import asyncio
import contextlib
import time
from collections import defaultdict, deque
from contextlib import asynccontextmanager
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from starlette.types import ASGIApp
from starlette.exceptions import HTTPException as StarletteHTTPException
from .auth import current_user
from .config import integer, limits, origins
from .files import EXTENSIONS, store
from .chat import ChatRequest, prepare_messages
from . import kaggle


async def cleaner():
    while True:
        await asyncio.sleep(60)
        await store.prune()


@asynccontextmanager
async def lifespan(app):
    task = asyncio.create_task(cleaner())
    try:
        yield
    finally:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task
        store.items.clear()


app = FastAPI(title='KIKO', docs_url=None, redoc_url=None, openapi_url=None, lifespan=lifespan)


@app.exception_handler(StarletteHTTPException)
async def http_error(request, exc):
    detail = str(exc.detail) if isinstance(exc, HTTPException) else {404: 'Recurso não encontrado.', 405: 'Método não permitido.'}.get(exc.status_code, 'Pedido inválido. Verifique os ficheiros enviados.')
    return JSONResponse({'error': {'message': detail}}, status_code=exc.status_code, headers=exc.headers)


@app.exception_handler(RequestValidationError)
async def validation_error(request, exc):
    # Pydantic errors may contain submitted conversation text: never echo them.
    return JSONResponse({'error': {'message': 'Pedido inválido. Verifique o modo, as mensagens e os limites de contexto.'}}, status_code=422)


@app.exception_handler(Exception)
async def unexpected_error(request, exc):
    return JSONResponse({'error': {'message': 'Erro interno do serviço. Tente novamente.'}}, status_code=500)


class BodyTooLarge(Exception):
    pass


class RequestGuard:
    """Authenticate before multipart parsing; cap even chunked HTTP bodies."""
    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http':
            return await self.app(scope, receive, send)
        path, method = scope['path'], scope['method']
        if not path.startswith('/api/') or path == '/api/health' or method == 'OPTIONS':
            return await self.app(scope, receive, send)
        request = Request(scope)
        try:
            await current_user(request, request.headers.get('authorization'))
            cap = limits()['max_file_bytes'] + 65536 if path == '/api/files' and method == 'POST' else 600000
            length = request.headers.get('content-length')
            if length and (not length.isdigit() or int(length) > cap):
                raise BodyTooLarge()
            count = 0
            async def bounded_receive():
                nonlocal count
                item = await receive()
                if item['type'] == 'http.request':
                    count += len(item.get('body', b''))
                    if count > cap:
                        raise HTTPException(413, 'Pedido ou ficheiro demasiado grande.')
                return item
            await self.app(scope, bounded_receive, send)
        except BodyTooLarge:
            await JSONResponse({'error': {'message': 'Pedido ou ficheiro demasiado grande.'}}, status_code=413)(scope, receive, send)
        except HTTPException as exc:
            await JSONResponse({'error': {'message': str(exc.detail)}}, status_code=exc.status_code, headers=exc.headers)(scope, receive, send)


class PrivateHeaders:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        async def secure_send(message):
            if message['type'] == 'http.response.start':
                message['headers'] = [(k, v) for k, v in message.get('headers', []) if k.lower() != b'cache-control'] + [(b'cache-control', b'no-store'), (b'x-content-type-options', b'nosniff')]
            await send(message)
        await self.app(scope, receive, secure_send)


app.add_middleware(RequestGuard)
app.add_middleware(PrivateHeaders)
app.add_middleware(CORSMiddleware, allow_origins=origins(), allow_credentials=False,
                   allow_methods=['GET', 'POST', 'DELETE'], allow_headers=['Authorization', 'Content-Type'], max_age=600)

_buckets = defaultdict(deque)
_active = set()


def rate(uid, kind, default=20):
    now = time.monotonic()
    bucket = _buckets[(uid, kind)]
    while bucket and bucket[0] < now - 60:
        bucket.popleft()
    maximum = integer('RATE_LIMIT_PER_MINUTE', default, 120)
    if len(bucket) >= maximum:
        raise HTTPException(429, 'Limite de pedidos atingido. Aguarde um minuto.', headers={'Retry-After': '60'})
    bucket.append(now)


@app.get('/api/health')
async def health():
    return {'status': 'ok'}


@app.get('/api/me')
async def me(user=Depends(current_user)):
    return {'uid': user['uid'], 'email': user.get('email', ''), 'limits': limits(), 'extensions': sorted(EXTENSIONS)}


@app.post('/api/chat')
async def chat(data: ChatRequest, user=Depends(current_user)):
    uid = user['uid']
    rate(uid, 'chat')
    if uid in _active or len(_active) >= 4:
        raise HTTPException(429, 'Já existe uma resposta em curso. Interrompa-a ou aguarde.')
    _active.add(uid)
    try:
        messages = await prepare_messages(data, uid)
        response = await kaggle.complete(messages, data.stream)
        if isinstance(response, StreamingResponse):
            async def release():
                _active.discard(uid)
            response.cleanups.append(release)
            return response
        _active.discard(uid)
        return response
    except BaseException:
        _active.discard(uid)
        raise


@app.post('/api/files')
async def upload(request: Request, user=Depends(current_user)):
    rate(user['uid'], 'upload')
    # No generic File dependency: authentication runs before body/spool allocation.
    async with request.form(max_files=1, max_fields=0) as form:
        entries = form.getlist('file')
        if len(entries) != 1 or not hasattr(entries[0], 'read'):
            raise HTTPException(422, 'Selecione um ficheiro para anexar.')
        file = entries[0]
        cap = limits()['max_file_bytes']
        data = await file.read(cap + 1)
        if len(data) > cap:
            raise HTTPException(413, 'O ficheiro excede o tamanho permitido.')
        return await store.save(user['uid'], file.filename, data)


@app.get('/api/files/{file_id}')
async def file_info(file_id: str, user=Depends(current_user)):
    return store.public(await store.get(user['uid'], file_id))


@app.delete('/api/files/{file_id}')
async def delete_file(file_id: str, user=Depends(current_user)):
    await store.delete(user['uid'], file_id)
    return {'deleted': True}
