"""UTF-8 SSE framing, normalised public events, and cancellation-safe closing."""
import json
import anyio
import httpx
from fastapi.responses import StreamingResponse

HEADERS = {'Cache-Control': 'no-store, no-transform', 'X-Accel-Buffering': 'no', 'X-Content-Type-Options': 'nosniff'}


def event(name, body):
    return f'event: {name}\ndata: {json.dumps(body, ensure_ascii=False, separators=(",", ":"))}\n\n'.encode()


async def close_upstream(response, client):
    with anyio.CancelScope(shield=True):
        try:
            await response.aclose()
        finally:
            await client.aclose()


async def sse_data(lines):
    parts = []
    size = 0
    async for line in lines:
        if not line:
            if parts:
                yield '\n'.join(parts)
            parts, size = [], 0
        elif line.startswith('data:'):
            value = line[5:].removeprefix(' ')
            size += len(value)
            if size > 1000000:
                raise ValueError('Oversized upstream event')
            parts.append(value)
    if parts:
        yield '\n'.join(parts)


async def relay(response, client):
    try:
        yield event('meta', {'streaming': True})
        finished = False
        async for raw in sse_data(response.aiter_lines()):
            if raw.strip() == '[DONE]':
                finished = True
                break
            body = json.loads(raw)
            if not isinstance(body, dict) or body.get('error'):
                raise ValueError('Upstream error')
            choices = body.get('choices', [])
            if not choices:
                continue
            choice = choices[0]
            delta = choice.get('delta', {}).get('content')
            if isinstance(delta, str) and delta:
                yield event('delta', {'text': delta})
            if choice.get('finish_reason'):
                finished = True
        if not finished:
            raise ValueError('Truncated stream')
        yield event('done', {})
    except (httpx.HTTPError, ValueError, TypeError, KeyError, AttributeError):
        yield event('error', {'message': 'A ligação ao modelo foi interrompida. Pode tentar novamente.'})
    finally:
        await close_upstream(response, client)


def fallback(text):
    # One complete response, with an explicit flag. No artificial token animation.
    yield event('meta', {'streaming': False})
    yield event('delta', {'text': text})
    yield event('done', {})


class ManagedStreamingResponse(StreamingResponse):
    """Own resources even if HTTP disconnects before the iterator starts."""
    def __init__(self, *args, cleanup=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.cleanups = [cleanup] if cleanup else []

    async def __call__(self, scope, receive, send):
        try:
            await super().__call__(scope, receive, send)
        finally:
            with anyio.CancelScope(shield=True):
                try:
                    if hasattr(self.body_iterator, 'aclose'):
                        await self.body_iterator.aclose()
                finally:
                    for cleanup in self.cleanups:
                        try:
                            await cleanup()
                        except Exception:
                            # Always run later releases, including the per-user gate.
                            continue
