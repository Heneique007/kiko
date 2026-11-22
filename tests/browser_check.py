"""Real Chromium UI, mocked Firebase/Kaggle network. No production test bypass."""
import contextlib
import http.server
import json
import re
import shutil
import threading
from pathlib import Path
from playwright.sync_api import sync_playwright, expect

ROOT = Path(__file__).resolve().parents[1]
class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs): super().__init__(*args, directory=str(ROOT), **kwargs)
    def log_message(self, *args): pass

CONFIG = """export const config = {apiBaseUrl: location.origin, firebase: {apiKey:'test', authDomain:'test.firebaseapp.com', projectId:'test', appId:'test'}};"""
APP = "export function initializeApp(config) {return config;}"
AUTH = """
const auth={currentUser:null};let callback;
export const browserLocalPersistence={};
export function getAuth(){return auth;}
export async function setPersistence(){}
export function onAuthStateChanged(a, cb){callback=cb;queueMicrotask(()=>cb(a.currentUser));return ()=>{};}
export async function signInWithEmailAndPassword(a,email,password){if(password!=='correct-password'){const e=new Error('invalid');e.code='auth/invalid-credential';throw e;}a.currentUser={email, getIdToken:async()=> 'mock-token'};callback(a.currentUser);}
export async function signOut(a){a.currentUser=null;callback(null);}
export async function sendPasswordResetEmail(){}
"""
ME = {'uid':'u1','email':'user@example.org','limits':{'max_file_bytes':10485760,'max_total_bytes':52428800,'max_files':20,'file_ttl_hours':6,'max_doc_chars':35000,'max_context_chars':120000,'max_attachments':4},'extensions':['.png','.jpg','.heic','.txt','.pdf','.docx','.xlsx','.pptx']}
SSE = 'event: meta\ndata: {"streaming":true}\n\nevent: delta\ndata: '+json.dumps({'text':'Olá! **Resposta segura.**\n\n| A | B |\n|---|---|\n| 1 | 2 |\n\n<script>window.xss=1</script>\n[Perigo](javascript:alert(1))'},ensure_ascii=False)+'\n\nevent: done\ndata: {}\n\n'


def main():
    server=http.server.ThreadingHTTPServer(('127.0.0.1',0),QuietHandler)
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    base=f'http://127.0.0.1:{server.server_port}'
    checks=[]
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=True, executable_path=shutil.which('chromium'), args=['--no-sandbox'])
        for width,height in [(320,740),(390,844),(1440,1000)]:
            context=browser.new_context(viewport={'width':width,'height':height},device_scale_factor=1,service_workers='block',is_mobile=width<600,has_touch=width<600)
            page=context.new_page();errors=[];sent=[];slow={'enabled':False};pending=[]
            page.on('pageerror',lambda error:errors.append(str(error)))
            page.on('console',lambda msg:errors.append(msg.text) if msg.type=='error' else None)
            page.route('**/js/config.js',lambda route:route.fulfill(content_type='application/javascript',body=CONFIG))
            page.route('https://www.gstatic.com/firebasejs/13.4.0/firebase-app.js',lambda route:route.fulfill(content_type='application/javascript',body=APP))
            page.route('https://www.gstatic.com/firebasejs/13.4.0/firebase-auth.js',lambda route:route.fulfill(content_type='application/javascript',body=AUTH))
            page.route('**/api/me',lambda route:route.fulfill(content_type='application/json',body=json.dumps(ME)))
            def respond(route):
                body=json.loads(route.request.post_data);sent.append(body)
                if slow['enabled']: pending.append(route);return
                route.fulfill(content_type='text/event-stream',body=SSE)
            page.route('**/api/chat',respond)
            page.route(re.compile(r'.*/api/files$'),lambda route:route.fulfill(content_type='application/json',body=json.dumps({'id':'file-test','filename':'notas.txt','bytes':5,'expires_at':9999999999,'kind':'text','truncated':False})))
            page.route('**/api/files/*',lambda route:route.fulfill(content_type='application/json',body='{"deleted":true}'))
            page.goto(base+'/frontend/');page.wait_for_load_state('networkidle')
            expect(page.locator('#login-view')).to_be_visible()
            page.locator('#email').fill('user@example.org');page.locator('#password').fill('wrong-password');page.locator('#login-submit').click()
            expect(page.locator('#login-error')).to_contain_text('incorretos')
            page.locator('#toggle-password').click();assert page.locator('#password').get_attribute('type')=='text'
            page.locator('#password').fill('correct-password');page.locator('#login-submit').click();expect(page.locator('#chat-view')).to_be_visible()
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
            page.locator('[data-select-mode="learn"]').click();expect(page.locator('[data-mode="learn"]')).to_have_attribute('aria-pressed','true')
            page.locator('#message-input').fill('Explique uma ideia.');page.locator('#send-button').click()
            expect(page.locator('.message-content')).to_contain_text('Resposta segura.')
            expect(page.locator('#send-button')).to_be_visible()
            assert sent[0]['mode']=='learn' and len(sent[0]['messages'])==1
            assert page.evaluate('window.xss') is None and page.locator('.message-content script').count()==0
            assert page.locator('.message-content a[href^="javascript:"]').count()==0
            assert page.locator('.table-scroll table').count()==1
            page.locator('[data-mode="quick"]').click();page.locator('#message-input').fill('Agora mais simples.');page.locator('#send-button').click()
            expect(page.locator('.message.assistant')).to_have_count(2)
            expect(page.locator('.message-status').last).to_have_text('Resposta concluída.')
            assert sent[1]['mode']=='quick' and [x['role'] for x in sent[1]['messages']]==['user','assistant','user']
            page.locator('.regenerate-button').last.click();expect(page.locator('.message-status').last).to_have_text('Resposta concluída.');assert len(sent)==3
            page.locator('#file-input').set_input_files({'name':'notas.txt','mimeType':'text/plain','buffer':b'notas'})
            expect(page.locator('.attachment-state')).to_contain_text('pronto')
            page.locator('#message-input').fill('Leia o anexo.');page.locator('#send-button').click();expect(page.locator('.message-status').last).to_have_text('Resposta concluída.')
            assert sent[-1]['messages'][-1]['file_ids']==['file-test']
            page.locator('#new-chat').click();expect(page.locator('#welcome')).to_be_visible();assert page.locator('.message').count()==0
            slow['enabled']=True;page.locator('#message-input').fill('Interromper teste');page.locator('#send-button').click();expect(page.locator('#stop-button')).to_be_visible();page.locator('#stop-button').click();expect(page.locator('#send-button')).to_be_visible()
            expect(page.locator('.message-status')).to_contain_text('interrompida')
            for route in pending:
                with contextlib.suppress(Exception):route.abort()
            page.locator('#new-chat').click();slow['enabled']=False
            page.locator('#message-input').fill('Depois de parar');page.locator('#send-button').click();expect(page.locator('.message-status')).to_have_text('Resposta concluída.')
            if width<600:
                page.set_viewport_size({'width':width,'height':420});page.locator('#message-input').focus()
                assert page.locator('#composer').bounding_box()['y']+page.locator('#composer').bounding_box()['height']<=421
                page.set_viewport_size({'width':width,'height':height})
            context.set_offline(True);expect(page.locator('#network-banner')).to_be_visible();context.set_offline(False);expect(page.locator('#network-banner')).to_be_hidden()
            page.locator('#account-toggle').click();page.locator('#logout').click();expect(page.locator('#login-view')).to_be_visible();assert page.locator('.message').count()==0
            assert not errors, errors
            checks.append(f'{width}x{height}: login, autorização simulada, modos, contexto, Markdown/XSS, anexos, regeneração, parar, nova conversa, logout e viewport: OK')
            context.close()
        # Unconfigured production distribution: actionable message, no API requests.
        context=browser.new_context(viewport={'width':1440,'height':1000},service_workers='block')
        page=context.new_page();page.goto(base+'/frontend/');expect(page.locator('#login-error')).to_contain_text('configuração inicial')
        Path('/tmp/kiko-login.png').parent.mkdir(exist_ok=True)
        page.screenshot(path='/tmp/kiko-login.png',full_page=True)
        context.close();browser.close()
    server.shutdown()
    print('\n'.join(checks));print('Unconfigured distribution: OK. External Firebase/Kaggle calls were mocked.')
if __name__=='__main__':main()
