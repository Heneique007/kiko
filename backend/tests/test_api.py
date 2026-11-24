import asyncio
import io
import json
import time
from pathlib import Path
import httpx
import pytest
from PIL import Image
from fastapi import HTTPException
from fastapi.responses import JSONResponse
from app import auth, chat, config, kaggle, main, prompts, streaming
from app.files import prepare_file, store
from conftest import MODEL, headers, payload


def test_public_health_and_no_legacy(client):
    assert client.get('/api/health').json() == {'status':'ok'}
    for path in ['/models','/files','/v1/models','/docs']:
        assert client.get(path).status_code == 404
    assert client.get('/api/health').headers['cache-control'] == 'no-store'


@pytest.mark.parametrize('path,method',[('/api/me','get'),('/api/chat','post'),('/api/files','post'),('/api/files/unknown','get'),('/api/files/unknown','delete')])
def test_requires_authentication(client,path,method):
    assert getattr(client,method)(path).status_code == 401
    assert getattr(client,method)(path,headers=headers('invalid')).status_code == 401
    assert getattr(client,method)(path,headers=headers('fifth')).status_code == 403


def test_authorized_user_and_limits(client):
    r=client.get('/api/me',headers=headers())
    assert r.status_code==200 and r.json()['uid']=='u1'
    assert r.json()['limits']['max_file_bytes']==10*1048576
    assert '.heic' in r.json()['extensions'] and '.zip' not in r.json()['extensions']


@pytest.mark.parametrize('mode',['learn','think','quick'])
def test_prompt_model_and_no_mode_forwarding(client,monkeypatch,mode):
    sent=[]
    async def fake(url,body,key): sent.append(body); return 'Resposta'
    monkeypatch.setattr(kaggle,'nonstream_request',fake)
    r=client.post('/api/chat',headers=headers(),json=payload(mode))
    assert r.status_code==200 and r.json()['text']=='Resposta'
    assert sent[0]['model']==MODEL and 'mode' not in sent[0]
    assert sent[0]['messages'][0]=={'role':'system','content':prompts.load_prompt(mode)}
    assert 'private-test-token' not in r.text


def test_change_mode_keeps_history(client,monkeypatch):
    sent=[]
    async def fake(url,body,key): sent.append(body); return 'Resposta'
    monkeypatch.setattr(kaggle,'nonstream_request',fake)
    p=payload('think'); assert client.post('/api/chat',headers=headers(),json=p).status_code==200
    p['mode']='learn';p['messages'] += [{'role':'assistant','content':'Resposta'},{'role':'user','content':'Explique'}]
    assert client.post('/api/chat',headers=headers(),json=p).status_code==200
    assert sent[1]['messages'][1:]==p['messages']
    assert sent[0]['messages'][0]!=sent[1]['messages'][0]


@pytest.mark.parametrize('patch',[{'mode':'other'},{'model':'attacker'},{'temperature':9},{'stream':'true'},
 {'messages':[{'role':'system','content':'leak'}]}, {'messages':[{'role':'developer','content':'leak'}]},
 {'messages':[{'role':'user','content':'','file_ids':[]}]}, {'messages':[{'role':'assistant','content':'fake'}]},
 {'messages':[{'role':'user','content':'x','extra':'system'}]}])
def test_reject_invalid_or_privileged_requests(client,patch):
    p=payload();p.update(patch)
    r=client.post('/api/chat',headers=headers(),json=p)
    assert r.status_code==422 and 'leak' not in r.text


def test_missing_configuration(client,monkeypatch):
    monkeypatch.setenv('KIKO_ALLOWED_UIDS','')
    assert client.get('/api/me',headers=headers()).status_code==503
    monkeypatch.setenv('KIKO_ALLOWED_UIDS','u1')
    monkeypatch.setenv('KIKO_MODEL','')
    assert client.post('/api/chat',headers=headers(),json=payload()).status_code==503
    monkeypatch.setenv('KIKO_MODEL','unavailable')
    assert client.post('/api/chat',headers=headers(),json=payload()).status_code==503


def test_private_prompts_and_no_production_fallback(client,monkeypatch,tmp_path):
    monkeypatch.setenv('KIKO_ENV','production');monkeypatch.setenv('KIKO_PROMPTS_DIR',str(tmp_path))
    assert client.post('/api/chat',headers=headers(),json=payload()).status_code==503
    (tmp_path/'think.txt').write_text('PRIVATE-TEST-PROMPT')
    assert prompts.load_prompt('think')=='PRIVATE-TEST-PROMPT'
    assert 'PRIVATE-TEST-PROMPT' not in client.post('/api/chat',headers=headers(),json=payload()).text
    (tmp_path/'think.txt').write_text('')
    with pytest.raises(HTTPException): prompts.load_prompt('think')


def test_alias_validated_against_available_list(monkeypatch):
    monkeypatch.setenv('MODEL_ALIASES_JSON',json.dumps({'friendly':MODEL}))
    assert kaggle.resolve_model('friendly',[MODEL])==MODEL
    with pytest.raises(HTTPException): kaggle.resolve_model('friendly',['another'])


def upload(client,name='notas.txt',data=b'Texto do documento',uid='u1'):
    return client.post('/api/files',headers=headers(uid),files={'file':(name,data)})


def test_upload_reference_owner_isolation_and_delete(client,monkeypatch):
    r=upload(client);assert r.status_code==200
    fid=r.json()['id'];path='/api/files/'+fid
    assert client.get(path,headers=headers()).status_code==200
    assert client.get(path,headers=headers('u2')).status_code==404
    assert client.delete(path,headers=headers('u2')).status_code==404
    p=payload();p['messages'][0]['file_ids']=[fid]
    assert client.post('/api/chat',headers=headers('u2'),json=p).status_code==404
    sent=[]
    async def fake(url,body,key): sent.append(body);return 'Documento lido'
    monkeypatch.setattr(kaggle,'nonstream_request',fake)
    assert client.post('/api/chat',headers=headers(),json=p).status_code==200
    assert 'Texto do documento' in sent[0]['messages'][1]['content'][1]['text']
    assert client.delete(path,headers=headers()).json()=={'deleted':True}
    assert client.get(path,headers=headers()).status_code==404


def test_expiry(client):
    fid=upload(client).json()['id'];store.items[fid]['expires_at']=time.time()-1
    assert client.get('/api/files/'+fid,headers=headers()).status_code==404
    assert fid not in store.items


@pytest.mark.parametrize('name,data,status',[('bad.png',b'not png',422),('bad.exe',b'MZ',415),('file.zip',b'PK',415),('empty.txt',b'',422),('bad.json',b'{bad}',422),('bad.txt',b'a\x00b',422)])
def test_invalid_files(client,name,data,status): assert upload(client,name,data).status_code==status


def test_file_size_and_storage_limits(client,monkeypatch):
    monkeypatch.setenv('MAX_FILE_MB','1');assert upload(client,data=b'x'*(1048576+1)).status_code==413
    monkeypatch.setenv('MAX_FILES','1');assert upload(client).status_code==200;assert upload(client).status_code==413


def test_image_is_decoded_converted_and_owned(client):
    buf=io.BytesIO();Image.new('RGB',(12,12),'red').save(buf,format='PNG')
    fid=upload(client,'a.png',buf.getvalue()).json()['id']
    part=asyncio.run(store.part('u1',fid));assert part['image_url']['url'].startswith('data:image/jpeg;base64,')


def test_documents_pdf_docx_xlsx_pptx():
    from docx import Document
    from openpyxl import Workbook
    from pptx import Presentation
    from reportlab.pdfgen import canvas
    buffers={}
    buf=io.BytesIO();doc=Document();doc.add_paragraph('Texto DOCX');doc.save(buf);buffers['.docx']=buf.getvalue()
    buf=io.BytesIO();book=Workbook();book.active.append(['Texto XLSX',123]);book.save(buf);buffers['.xlsx']=buf.getvalue()
    buf=io.BytesIO();pres=Presentation();slide=pres.slides.add_slide(pres.slide_layouts[1]);slide.shapes.title.text='Texto PPTX';pres.save(buf);buffers['.pptx']=buf.getvalue()
    buf=io.BytesIO();pdf=canvas.Canvas(buf);pdf.drawString(20,700,'Texto PDF');pdf.save();buffers['.pdf']=buf.getvalue()
    for ext,data in buffers.items(): assert 'Texto' in prepare_file(data,ext)[1]


def test_rate_context_body_and_no_sensitive_validation_echo(client,monkeypatch):
    monkeypatch.setenv('RATE_LIMIT_PER_MINUTE','1')
    assert client.post('/api/chat',headers=headers(),json=payload()).status_code==200
    assert client.post('/api/chat',headers=headers(),json=payload()).status_code==429
    r=client.post('/api/chat',headers=headers(),content=b'x'*(config.limits()['max_context_chars']*6+65536+1));assert r.status_code==413
    p=payload();p['messages'][0]['content']='SECRET'*27000+'x'
    r=client.post('/api/chat',headers=headers(),json=p);assert r.status_code==422 and 'SECRET' not in r.text


def test_fallback_stream_not_artificially_chunked(client,monkeypatch):
    monkeypatch.setenv('STREAM_MODE','emulate')
    r=client.post('/api/chat',headers=headers(),json=payload(stream=True))
    assert r.status_code==200 and 'event: meta' in r.text and '"streaming":false' in r.text
    assert r.text.count('event: delta')==1 and 'event: done' in r.text
    assert not main._active


class FakeClient:
    status=200; mime='text/event-stream'; raw=None; closed=False; response_closed=False; captured=[]
    def __init__(self,**kwargs): pass
    def build_request(self,method,url,**kwargs):
        type(self).captured.append(kwargs['json']);return httpx.Request(method,url,**kwargs)
    async def send(self,request,stream=False):
        cls=type(self)
        class Source(httpx.AsyncByteStream):
            async def __aiter__(self):
                content=cls.raw if cls.raw is not None else 'data: {"choices":[{"delta":{"content":"Olá 🧡"}}]}\r\n\r\ndata: [DONE]\n\n'.encode()
                for i in range(0,len(content),3): yield content[i:i+3]
            async def aclose(self): cls.response_closed=True
        return httpx.Response(cls.status,headers={'content-type':cls.mime},request=request,stream=Source())
    async def aclose(self): type(self).closed=True


def fake_client(monkeypatch,**changes):
    for key,value in {'status':200,'mime':'text/event-stream','raw':None,'closed':False,'response_closed':False,'captured':[],**changes}.items(): monkeypatch.setattr(FakeClient,key,value)
    monkeypatch.setattr(kaggle.httpx,'AsyncClient',FakeClient)


def test_native_stream_fragments_unicode_and_release(client,monkeypatch):
    fake_client(monkeypatch)
    r=client.post('/api/chat',headers=headers(),json=payload(stream=True))
    assert r.status_code==200 and 'Olá 🧡' in r.text and 'event: done' in r.text
    assert FakeClient.closed and FakeClient.response_closed and not main._active
    assert FakeClient.captured[0]['model']==MODEL and 'mode' not in FakeClient.captured[0]


@pytest.mark.parametrize('status,mime,raw',[(400,'application/json',b'{"error":"stream unsupported"}'),(200,'application/json',b'{"choices":[{"message":{"content":"Complete"}}]}')])
def test_auto_fallback(client,monkeypatch,status,mime,raw):
    fake_client(monkeypatch,status=status,mime=mime,raw=raw)
    r=client.post('/api/chat',headers=headers(),json=payload(stream=True))
    assert r.status_code==200 and '"streaming":false' in r.text and 'event: done' in r.text
    assert FakeClient.closed and FakeClient.response_closed


def test_upstream_errors_sanitized(client,monkeypatch):
    fake_client(monkeypatch,status=500,mime='application/json',raw=b'{"secret":"do-not-echo"}')
    r=client.post('/api/chat',headers=headers(),json=payload(stream=True))
    assert r.status_code==502 and 'do-not-echo' not in r.text and not main._active
    fake_client(monkeypatch,status=429)
    assert client.post('/api/chat',headers=headers(),json=payload(stream=True)).status_code==429


def test_truncated_stream_reports_error(client,monkeypatch):
    fake_client(monkeypatch,raw=b'data: {"choices":[{"delta":{"content":"partial"}}]}\n\n')
    r=client.post('/api/chat',headers=headers(),json=payload(stream=True))
    assert 'partial' in r.text and 'event: error' in r.text and 'event: done' not in r.text
    assert FakeClient.closed and FakeClient.response_closed


@pytest.mark.asyncio
async def test_cancelled_relay_releases_connections():
    class Response:
        closed=False
        async def aiter_lines(self):
            yield 'data: {"choices":[{"delta":{"content":"text"}}]}'
            yield ''
            await asyncio.Event().wait()
        async def aclose(self): self.closed=True
    class Client:
        closed=False
        async def aclose(self): self.closed=True
    response=Response();client=Client();iterator=streaming.relay(response,client)
    await anext(iterator);await anext(iterator)
    task=asyncio.create_task(anext(iterator));await asyncio.sleep(0);task.cancel()
    with pytest.raises(asyncio.CancelledError): await task
    assert response.closed and client.closed


def test_firebase_real_verifier_rejects_bad_signature(monkeypatch):
    monkeypatch.setattr(auth,'admin_app',lambda:object())
    monkeypatch.setattr(auth.auth,'verify_id_token',lambda *a,**kw: (_ for _ in ()).throw(ValueError('PRIVATE')))
    with pytest.raises(HTTPException) as e: auth.verify_token('invalid')
    assert e.value.status_code==401 and 'PRIVATE' not in e.value.detail


def test_cors_rejects_wildcard(monkeypatch):
    monkeypatch.setenv('CORS_ORIGINS','*')
    with pytest.raises(RuntimeError): config.origins()
    monkeypatch.setenv('CORS_ORIGINS','https://person.github.io,http://localhost:5500')
    assert len(config.origins())==2

@pytest.mark.asyncio
async def test_stream_cleanup_before_first_body_frame():
    called=[]
    async def body():
        yield b'never sent'
    async def cleanup(): called.append(True)
    response=streaming.ManagedStreamingResponse(body(),cleanup=cleanup)
    async def fail_send(message): raise RuntimeError('connection lost before body')
    async def receive(): return {'type':'http.disconnect'}
    with pytest.raises(Exception):
        await response({'type':'http','method':'POST','asgi':{'spec_version':'2.4'}},receive,fail_send)
    assert called==[True]


def test_all_four_accounts_authorized(client):
    for uid in ('u1','u2','u3','u4'): assert client.get('/api/me',headers=headers(uid)).status_code==200


def test_explicit_local_prompts_take_priority(client,monkeypatch,tmp_path):
    for mode in prompts.MODES: (tmp_path/f'{mode}.txt').write_text(f'private {mode}')
    monkeypatch.setenv('KIKO_PROMPTS_DIR',str(tmp_path))
    for mode in prompts.MODES: assert prompts.load_prompt(mode)==f'private {mode}'


def test_context_total_and_reject_duplicate_attachment(client,monkeypatch):
    monkeypatch.setenv('MAX_CONTEXT_CHARS','10')
    p=payload();p['messages'][0]['content']='x'*11
    assert client.post('/api/chat',headers=headers(),json=p).status_code==422
    p=payload();p['messages'][0]['file_ids']=['file-a','file-a']
    assert client.post('/api/chat',headers=headers(),json=p).status_code==422


def test_office_archive_bomb_rejected():
    import zipfile
    from app.files import validate_office
    buf=io.BytesIO()
    with zipfile.ZipFile(buf,'w',zipfile.ZIP_DEFLATED) as z:
        z.writestr('word/document.xml','x'*100000)
    with pytest.raises(ValueError): validate_office(buf.getvalue(),'.docx')


def test_kaggle_cli_real_initialization_parser(monkeypatch,tmp_path):
    from types import SimpleNamespace
    def run(argv,**kwargs):
        assert argv[:4]==['kaggle','benchmarks','init','-y']
        envfile=Path(argv[argv.index('--env-file')+1])
        envfile.write_text('MODEL_PROXY_URL=https://proxy.test/models\nMODEL_PROXY_API_KEY=TEMPORARY\nLLMS_AVAILABLE=test/z,test/a,test/z\nMODEL_PROXY_EXPIRY_TIME=2099-01-01T00:00:00Z\n')
        return SimpleNamespace(returncode=0,stdout='',stderr='')
    monkeypatch.setattr(kaggle.subprocess,'run',run)
    result=kaggle.obtain()
    assert result['models']==['test/a','test/z'] and result['key']=='TEMPORARY'
    assert result['url']=='https://proxy.test/models'


def test_cli_failure_hides_raw_secrets(monkeypatch,capsys):
    from types import SimpleNamespace
    monkeypatch.setattr(kaggle.subprocess,'run',lambda *a,**kw:SimpleNamespace(returncode=1,stdout='SECRET-TOKEN',stderr='401 unauthorized'))
    with pytest.raises(RuntimeError): kaggle.obtain()
    assert 'SECRET-TOKEN' not in capsys.readouterr().out


def test_firebase_service_config_not_public(monkeypatch):
    monkeypatch.setenv('FIREBASE_PROJECT_ID','')
    monkeypatch.delenv('GOOGLE_APPLICATION_CREDENTIALS',raising=False)
    monkeypatch.delenv('FIREBASE_SERVICE_ACCOUNT_JSON',raising=False)
    with pytest.raises(HTTPException) as exc: auth.admin_app()
    assert exc.value.status_code==503


@pytest.mark.asyncio
async def test_auth_provider_and_revocation_check(monkeypatch):
    monkeypatch.setattr(auth,'admin_app',lambda: 'app')
    calls=[]
    def verify(token,**kwargs):
        calls.append(kwargs);return {'uid':'u1','firebase':{'sign_in_provider':'google.com'}}
    monkeypatch.setattr(auth.auth,'verify_id_token',verify)
    with pytest.raises(HTTPException) as exc: auth.verify_token('token')
    assert exc.value.status_code==403 and calls[0]['check_revoked'] is True


def test_unknown_environment_cannot_enable_example_prompts(client,monkeypatch,tmp_path):
    monkeypatch.setenv('KIKO_ENV','prod')
    monkeypatch.setenv('KIKO_PROMPTS_DIR',str(tmp_path))
    with pytest.raises(HTTPException):prompts.load_prompt('think')


def test_emulator_tokens_never_enabled_by_accident(monkeypatch):
    monkeypatch.setenv('FIREBASE_AUTH_EMULATOR_HOST','localhost:9099')
    with pytest.raises(HTTPException) as exc:auth.admin_app()
    assert exc.value.status_code==503


@pytest.mark.asyncio
@pytest.mark.parametrize('context_chars', [120000, 300000])
@pytest.mark.parametrize('extra, expected', [(0, 422), (1, 413)])
async def test_chunked_body_limit(client, monkeypatch, context_chars, extra, expected):
    monkeypatch.setenv('MAX_CONTEXT_CHARS', str(context_chars))
    transport = httpx.ASGITransport(app=main.app)
    cap = context_chars * 6 + 65536
    async def body():
        remaining = cap + extra
        while remaining:
            size = min(100000, remaining)
            yield b'x' * size
            remaining -= size
    async with httpx.AsyncClient(transport=transport, base_url='http://test') as http:
        r = await http.post('/api/chat', headers={**headers(), 'Content-Type':'application/json'}, content=body())
    # Exactly at the cap: invalid JSON (422). One byte over: body limit (413).
    assert r.status_code == expected
    assert not main._active
    assert not main._buckets


def test_rolling_upload_quota_per_uid(client, monkeypatch):
    monkeypatch.setenv('MAX_UPLOADS_PER_3H', '2')
    assert upload(client).status_code == 200
    assert upload(client).status_code == 200
    assert upload(client).status_code == 429
    assert upload(client, uid='u2').status_code == 200


def test_image_size_limit_independent_of_document_limit(client, monkeypatch):
    monkeypatch.setenv('MAX_FILE_MB', '50')
    monkeypatch.setenv('MAX_IMAGE_MB', '1')
    assert upload(client, 'a.png', b'x' * (1048576 + 1)).status_code == 413
    assert upload(client, 'a.txt', b'x' * (1048576 + 1)).status_code == 200
