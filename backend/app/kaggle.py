"""Kaggle transport adapted from the supplied bridge; no legacy UI or API key."""
import asyncio
import json
import os
import re
import subprocess
import tempfile
from pathlib import Path
from datetime import datetime, timedelta, timezone
from urllib.parse import urlsplit
import httpx
from dotenv import dotenv_values
from fastapi import HTTPException
from fastapi.responses import JSONResponse, StreamingResponse
from .streaming import HEADERS, ManagedStreamingResponse, close_upstream, fallback, relay

_lock = asyncio.Lock()
_state = {}
DEFAULT_ALIASES = {
    'Claude Sonnet 5': 'anthropic/claude-sonnet-5@default',
    'DeepSeek R1': 'deepseek-ai/deepseek-r1-0528',
    'Gemini 3 Flash': 'google/gemini-3-flash-preview',
    'Gemini 3.1 Flash Lite': 'google/gemini-3.1-flash-lite-preview',
    'Granite 4 Small': 'ibm/granite-4.0-h-small',
    'GPT 5.4 Nano': 'openai/gpt-5.4-nano-2026-03-17',
    'GPT OSS 120B': 'openai/gpt-oss-120b',
    'Qwen 3 Next 80B': 'qwen/qwen3-next-80b-a3b-instruct',
}

SHORT_ALIASES = {
    'claude-sonnet-5': 'anthropic/claude-sonnet-5@default',
    'deepseek-r1': 'deepseek-ai/deepseek-r1-0528',
    'gemini-3-flash': 'google/gemini-3-flash-preview',
    'gemini-3.1-flash-lite': 'google/gemini-3.1-flash-lite-preview',
    'granite-4-small': 'ibm/granite-4.0-h-small',
    'gpt-5.4-nano': 'openai/gpt-5.4-nano-2026-03-17',
    'gpt-oss-120b': 'openai/gpt-oss-120b',
    'qwen-3-next': 'qwen/qwen3-next-80b-a3b-instruct',
}

def expires_at(s):
    if not s:
        return datetime.now(timezone.utc) + timedelta(minutes=5)
    try:
        if str(s).isdigit():
            return datetime.fromtimestamp(int(s), timezone.utc)
        return datetime.fromisoformat(str(s).replace('Z', '+00:00')).astimezone(timezone.utc)
    except (ValueError, OverflowError):
        return datetime.now(timezone.utc) + timedelta(minutes=5)

def obtain():
    with tempfile.TemporaryDirectory() as tmp:
        envpath = Path(tmp) / 'kaggle.env'
        example = Path(tmp) / 'example_task.py'
        p = subprocess.run(
            ['kaggle', 'benchmarks', 'init', '-y', '--env-file', str(envpath), '--example-file', str(example)],
            cwd=tmp, capture_output=True, text=True, timeout=90,
            env={**os.environ, 'PYTHONUNBUFFERED': '1'},
        )
        if p.returncode:
            # Diagnostic labels only; don't log CLI raw output or proxy credentials.
            combined = ((p.stderr or '') + '\n' + (p.stdout or '')).lower()
            checks = [
                ('CLI_USAGE', ('no such command', 'no such option', 'unrecognized arguments')),
                ('AUTH_401', ('401', 'unauthorized', 'invalid api key', 'invalid token')),
                ('ACCESS_403', ('403', 'forbidden')),
                ('RATE_LIMIT', ('429', 'rate limit')),
                ('NETWORK', ('connectionerror', 'connection refused', 'name resolution', 'proxyerror', 'certificate')),
                ('TIMEOUT', ('timed out', 'timeout')),
                ('CLI_IMPORT', ('modulenotfounderror', 'importerror', 'no module named')),
                ('FILESYSTEM', ('permissionerror', 'read-only file system')),
            ]
            matched = [label for label, patterns in checks if any(pat in combined for pat in patterns)]
            missing = re.findall(r"No module named ['\"]([A-Za-z_][A-Za-z_0-9.]*)['\"]", (p.stderr or '') + '\n' + (p.stdout or ''))
            print('KAGGLE DIAGNOSTICO:', ', '.join(matched) if matched else 'UNKNOWN', flush=True)
            if missing:
                print('KAGGLE MODULO EM FALTA:', ', '.join(sorted(set(missing))[:5]), flush=True)
            print('KAGGLE INIT FAILED: returncode=', p.returncode, flush=True)
            raise RuntimeError('Kaggle initialization failed')
        vals = dotenv_values(envpath)
        url = (vals.get('MODEL_PROXY_URL') or '').strip()
        key = (vals.get('MODEL_PROXY_API_KEY') or '').strip()
        models = sorted(set(x.strip() for x in (vals.get('LLMS_AVAILABLE') or '').split(',') if x.strip()))
        parsed = urlsplit(url)
        if parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise RuntimeError('Kaggle returned an invalid Model Proxy URL')
        if not key or not models:
            raise RuntimeError('Kaggle did not return credentials and LLMS_AVAILABLE')
        return {'url': url.rstrip('/'), 'key': key, 'models': models,
                'expiry': expires_at(vals.get('MODEL_PROXY_EXPIRY_TIME'))}

async def credentials(force=False):
    async with _lock:
        if not force and _state and datetime.now(timezone.utc) + timedelta(minutes=2) < _state['expiry']:
            return dict(_state)
        try:
            new_state = await asyncio.to_thread(obtain)
        except Exception as e:
            print('KAGGLE ERROR:', type(e).__name__, flush=True)
            if _state and datetime.now(timezone.utc) < _state['expiry'] and not force:
                return dict(_state)
            raise HTTPException(503, 'Unable to refresh Kaggle credentials') from None
        _state.clear()
        _state.update(new_state)
        return dict(_state)

def alias_map() -> dict[str, str]:
    aliases = {**DEFAULT_ALIASES, **SHORT_ALIASES}
    raw = os.getenv('MODEL_ALIASES_JSON', '').strip()
    if raw:
        try:
            extra = json.loads(raw)
            if not isinstance(extra, dict) or len(extra) > 50:
                raise ValueError()
            for k, v in extra.items():
                if not isinstance(k, str) or not isinstance(v, str) or not 1 <= len(k) <= 90 or not 1 <= len(v) <= 160:
                    raise ValueError()
            aliases.update(extra)
        except (ValueError, TypeError):
            print('CONFIG ERROR: invalid MODEL_ALIASES_JSON; using defaults', flush=True)
    return aliases

def chat_path() -> str:
    path = os.getenv('KAGGLE_CHAT_PATH', '/openapi/v1/chat/completions')
    if not path.startswith('/') or '://' in path or '?' in path or '#' in path or '..' in path or '//' in path:
        raise HTTPException(503, 'Invalid KAGGLE_CHAT_PATH')
    return path

def client_timeout():
    return httpx.Timeout(connect=20.0, read=180.0, write=35.0, pool=20.0)


def resolve_model(configured, available):
    real = configured if configured in available else alias_map().get(configured)
    if not configured:
        raise HTTPException(503, 'KIKO_MODEL não está configurado no servidor.')
    if real not in available:
        raise HTTPException(503, 'O modelo configurado não está disponível nas credenciais Kaggle atuais.')
    return real


def completion_text(body):
    try:
        text = body['choices'][0]['message']['content']
        if not isinstance(text, str) or not text.strip():
            raise ValueError()
        return text
    except (KeyError, IndexError, TypeError, ValueError):
        raise HTTPException(502, 'O modelo devolveu uma resposta inválida ou vazia.') from None


def upstream_error(status):
    if status == 429:
        raise HTTPException(429, 'Limite do serviço de IA atingido. Aguarde antes de tentar novamente.')
    if status in (401, 403):
        raise HTTPException(502, 'O Kaggle recusou as credenciais temporárias. Tente novamente.')
    raise HTTPException(502, 'O serviço de IA está temporariamente indisponível.')


async def nonstream_request(url, body, key):
    async with httpx.AsyncClient(timeout=client_timeout(), follow_redirects=False) as client:
        try:
            response = await client.post(url, json={**body, 'stream': False}, headers={'Authorization': 'Bearer ' + key})
        except httpx.HTTPError:
            raise HTTPException(502, 'Não foi possível contactar o serviço de IA.') from None
    if response.is_error:
        upstream_error(response.status_code)
    try:
        return completion_text(response.json())
    except ValueError:
        raise HTTPException(502, 'Resposta inválida do serviço de IA.') from None


async def complete(messages, want_stream):
    configured = os.getenv('KIKO_MODEL', '').strip()
    if not configured or not os.getenv('KAGGLE_API_TOKEN', '').strip():
        raise HTTPException(503, 'Integração Kaggle por configurar no servidor.')
    mode = os.getenv('STREAM_MODE', 'auto').lower()
    if mode not in ('auto', 'native', 'emulate'):
        raise HTTPException(503, 'STREAM_MODE deve ser auto, native ou emulate.')
    c = await credentials()
    model = resolve_model(configured, c['models'])
    url = c['url'] + chat_path()
    body = {'model': model, 'messages': messages, 'stream': want_stream}
    if not want_stream or mode == 'emulate':
        text = await nonstream_request(url, body, c['key'])
        return ManagedStreamingResponse(fallback(text), media_type='text/event-stream', headers=HEADERS) if want_stream else JSONResponse({'text': text}, headers=HEADERS)
    client = httpx.AsyncClient(timeout=client_timeout(), follow_redirects=False)
    response = None
    try:
        req = client.build_request('POST', url, json=body, headers={'Authorization': 'Bearer ' + c['key']})
        response = await client.send(req, stream=True)
        if not response.is_error and 'text/event-stream' in response.headers.get('content-type', '').lower():
            return ManagedStreamingResponse(relay(response, client), cleanup=lambda: close_upstream(response, client), media_type='text/event-stream', headers=HEADERS)
        raw = await response.aread()
        status = response.status_code
        await close_upstream(response, client)
        response = None
        if status in (400, 422) and mode == 'auto' and b'stream' in raw.lower() and any(s in raw.lower() for s in (b'unsupported', b'not support', b'not available')):
            text = await nonstream_request(url, body, c['key'])
        elif status >= 400:
            upstream_error(status)
        else:
            try:
                text = completion_text(json.loads(raw))
            except ValueError:
                raise HTTPException(502, 'O serviço de IA não devolveu uma resposta válida.') from None
        return ManagedStreamingResponse(fallback(text), media_type='text/event-stream', headers=HEADERS)
    except BaseException as exc:
        if response is not None:
            await close_upstream(response, client)
        else:
            await client.aclose()
        if isinstance(exc, httpx.HTTPError):
            raise HTTPException(502, 'Não foi possível contactar o serviço de IA.') from None
        raise
