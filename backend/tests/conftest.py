import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pytest
import httpx
from datetime import datetime, timedelta, timezone
from fastapi import HTTPException
from fastapi.testclient import TestClient
from app import auth, kaggle, main
from app.files import store

MODEL = 'test/model-real'

@pytest.fixture
def client(monkeypatch):
    values = {'KIKO_ENV':'development', 'KIKO_ALLOW_EXAMPLE_PROMPTS':'true', 'KIKO_ALLOWED_UIDS':'u1,u2,u3,u4',
              'KIKO_MODEL':MODEL, 'KAGGLE_API_TOKEN':'private-test-token', 'STREAM_MODE':'auto',
              'RATE_LIMIT_PER_MINUTE':'120', 'MAX_FILE_MB':'10', 'MAX_TOTAL_MB':'50', 'MAX_FILES':'20',
              'FILE_TTL_HOURS':'6', 'MAX_DOC_CHARS':'35000', 'MAX_CONTEXT_CHARS':'120000', 'MAX_ATTACHMENTS':'4'}
    for k,v in values.items(): monkeypatch.setenv(k,v)
    monkeypatch.delenv('KIKO_PROMPTS_DIR', raising=False)
    monkeypatch.delenv('MODEL_ALIASES_JSON', raising=False)
    def verify(token):
        if token == 'invalid': raise HTTPException(401, 'Sessão inválida.')
        return {'uid': token, 'email': token+'@test.local', 'firebase': {'sign_in_provider':'password'}}
    monkeypatch.setattr(auth,'verify_token',verify)
    async def creds(force=False):
        return {'url':'https://proxy.test', 'key':'temporary-secret', 'models':[MODEL], 'expiry':datetime.now(timezone.utc)+timedelta(hours=1)}
    monkeypatch.setattr(kaggle,'credentials',creds)
    async def nonstream(url, body, key): return 'Olá, KIKO!'
    monkeypatch.setattr(kaggle,'nonstream_request',nonstream)
    store.items.clear(); main._active.clear(); main._buckets.clear()
    with TestClient(main.app) as client: yield client


def headers(uid='u1'): return {'Authorization':'Bearer '+uid}
def payload(mode='think', stream=False): return {'mode':mode,'messages':[{'role':'user','content':'Olá'}],'stream':stream}
