import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { build } from 'esbuild';
import { JSDOM, VirtualConsole } from 'jsdom';
const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const html = await fs.readFile(path.join(root, 'frontend/index.html'), 'utf8');
const fakeAuth = `const auth={currentUser:null};let callback;export const browserLocalPersistence={};export function getAuth(){return auth;}export async function setPersistence(){}export function onAuthStateChanged(a,cb){callback=cb;queueMicrotask(()=>cb(a.currentUser));}export async function signInWithEmailAndPassword(a,email,password){if(password!=='correct'){const e=new Error('invalid');e.code='auth/invalid-credential';throw e;}a.currentUser={email,getIdToken:async()=> 'test-token'};callback(a.currentUser);}export async function signOut(a){a.currentUser=null;callback(null);}export async function sendPasswordResetEmail(){}`;
const bundle = await build({ entryPoints: [path.join(root,'frontend/js/app.js')], bundle: true, write: false, format:'iife', target:'es2022', plugins:[{name:'test-only-external-fixtures',setup(b){
  b.onResolve({filter:/config\.js$/},() => ({path:'config',namespace:'fixture'}));
  b.onResolve({filter:/https:\/\/www\.gstatic\.com\//},args => ({path:args.path.includes('firebase-app.js')?'firebase-app':'firebase-auth',namespace:'fixture'}));
  b.onLoad({filter:/.*/,namespace:'fixture'},args => ({contents:args.path==='config'?`export const config={apiBaseUrl:'https://kiko.test',firebase:{apiKey:'public-test',authDomain:'test.firebaseapp.com',projectId:'test',appId:'test'}};`:args.path==='firebase-app'?'export function initializeApp(config){return config;}':fakeAuth,loader:'js'}));
}}] });
const code = bundle.outputFiles[0].text;
const me = {uid:'u1',email:'user@test.local',extensions:['.txt','.png'],limits:{max_file_bytes:10485760,max_total_bytes:52428800,max_files:20,file_ttl_hours:6,max_doc_chars:35000,max_context_chars:120000,max_attachments:4}};
const responseText = 'Olá! **Texto seguro.**\n\n| A | B |\n|---|---|\n| 1 | 2 |\n\n<script>window.xss=1</script>\n[Malicioso](javascript:alert(1))';
const event = (type,data) => `event: ${type}\ndata: ${JSON.stringify(data)}\n\n`;
const tick = () => new Promise(resolve=>setTimeout(resolve,5));
async function until(predicate){for(let i=0;i<400;i++){if(predicate())return;await tick();}assert.fail('UI condition timed out');}
async function harness(){
  const errors=[];const console=new VirtualConsole();console.on('jsdomError',e=>errors.push(String(e)));
  const dom=new JSDOM(html,{url:'https://kiko.test/kiko/',runScripts:'outside-only',pretendToBeVisual:true,virtualConsole:console});
  const w=dom.window;const calls=[];const state={slow:false,fail:false,cancelled:false};
  w.matchMedia=()=>({matches:false,addEventListener(){}});w.TextDecoder=TextDecoder;w.TextEncoder=TextEncoder;
  w.URL.createObjectURL=()=> 'blob:test';w.URL.revokeObjectURL=()=>{};w.document.execCommand=()=>true;
  w.fetch=async(url,options={})=>{
    if(options.signal?.aborted)throw options.signal.reason;
    calls.push({url,options});
    if(url.endsWith('/api/me'))return new Response(JSON.stringify(me));
    if(url.includes('/api/files/'))return new Response('{"deleted":true}');
    if(url.endsWith('/api/chat')){
      if(state.fail)return new Response('{"error":{"message":"Serviço indisponível de teste."}}',{status:503});
      let ctl;
      const body=new ReadableStream({start(controller){ctl=controller;controller.enqueue(new TextEncoder().encode(event('meta',{streaming:true})+event('delta',{text:responseText})));if(!state.slow){controller.enqueue(new TextEncoder().encode(event('done',{})));controller.close();}},cancel(){state.cancelled=true;}});
      options.signal?.addEventListener('abort',()=>{try{ctl.error(options.signal.reason);}catch{}});
      return new Response(body,{headers:{'content-type':'text/event-stream'}});
    }
    throw new Error('Unexpected test request '+url);
  };
  w.XMLHttpRequest=class{
    constructor(){this.upload={};this.status=200;}
    open(){} setRequestHeader(){}
    send(){setTimeout(()=>{this.upload.onprogress?.({lengthComputable:true,loaded:5,total:5});this.responseText=JSON.stringify({id:'file-test',filename:'notas.txt',bytes:5,kind:'text',expires_at:9999999999,truncated:false});this.onload?.();},0);}
    abort(){this.onabort?.();}
  };
  w.eval(code);await tick();
  const el=id=>w.document.getElementById(id);
  function input(id,value){el(id).value=value;el(id).dispatchEvent(new w.Event('input',{bubbles:true}));}
  function click(selector){const target=w.document.querySelector(selector);assert.ok(target,selector);target.click();}
  async function login(){input('email','user@test.local');input('password','correct');el('login-form').dispatchEvent(new w.Event('submit',{bubbles:true,cancelable:true}));await until(()=>!el('chat-view').hidden);}
  async function send(value){input('message-input',value);el('composer').dispatchEvent(new w.Event('submit',{bubbles:true,cancelable:true}));await until(()=>el('stop-button').hidden);}
  return {w,dom,el,input,click,login,send,calls,state,errors};
}

test('UI: real modules, login/error/password recovery, mode switching, history and safe Markdown',async()=>{
  const h=await harness();try{
    assert.equal(h.el('chat-view').hidden,true);
    h.input('email','user@test.local');h.input('password','wrong');h.el('login-form').dispatchEvent(new h.w.Event('submit',{cancelable:true}));await until(()=>!h.el('login-error').hidden);assert.match(h.el('login-error').textContent,/incorretos/);
    h.click('#toggle-password');assert.equal(h.el('password').type,'text');
    h.click('#reset-password');await until(()=>h.el('login-error').textContent.includes('recuperação'));
    await h.login();assert.equal(h.calls.filter(x=>x.url.endsWith('/api/chat')).length,0);
    h.click('[data-select-mode="learn"]');await h.send('Primeira pergunta');
    const first=JSON.parse(h.calls.find(x=>x.url.endsWith('/api/chat')).options.body);assert.equal(first.mode,'learn');
    assert.equal(h.w.document.querySelectorAll('.message-content strong').length,1);
    assert.equal(h.w.document.querySelectorAll('.table-scroll table').length,1);
    assert.equal(h.w.document.querySelectorAll('.message-content script').length,0);
    assert.equal(h.w.document.querySelectorAll('.message-content a[href^="javascript:"]').length,0);
    assert.equal(h.w.xss,undefined);
    h.click('[data-mode="quick"]');await h.send('Segunda pergunta');
    const sent=h.calls.filter(x=>x.url.endsWith('/api/chat')).map(x=>JSON.parse(x.options.body));
    assert.equal(sent[1].mode,'quick');assert.deepEqual(sent[1].messages.map(x=>x.role),['user','assistant','user']);
    h.click('.message.assistant:last-child .regenerate-button');await until(()=>h.el('stop-button').hidden);
    assert.equal(h.calls.filter(x=>x.url.endsWith('/api/chat')).length,3);
    h.click('.message.assistant:last-child .message-actions button');await until(()=>!h.el('toast').hidden);assert.equal(h.el('toast').textContent,'Texto copiado.');
    assert.deepEqual(h.errors,[]);
  }finally{h.dom.window.close();}
});

test('UI: stop preserves partial text, releases busy state, next message works, errors recover',async()=>{
  const h=await harness();try{
    await h.login();h.state.slow=true;h.input('message-input','Parar teste');h.el('composer').dispatchEvent(new h.w.Event('submit',{cancelable:true}));
    await until(()=>!h.el('stop-button').hidden);await until(()=>h.w.document.querySelector('.message-content')?.textContent.includes('Texto seguro'));
    h.click('#stop-button');await until(()=>h.el('stop-button').hidden);
    assert.match(h.w.document.querySelector('.message-status').textContent,/interrompida/);assert.match(h.w.document.querySelector('.message-content').textContent,/Texto seguro/);
    h.state.slow=false;await h.send('Depois da interrupção');assert.match(h.w.document.querySelector('.message.assistant:last-child .message-status').textContent,/concluída/);
    h.state.fail=true;await h.send('Gerar erro');assert.match(h.w.document.querySelector('.message.assistant:last-child .message-status').textContent,/indisponível/);
    h.state.fail=false;await h.send('Recuperar');assert.match(h.w.document.querySelector('.message.assistant:last-child .message-status').textContent,/concluída/);
    assert.deepEqual(h.errors,[]);
  }finally{h.dom.window.close();}
});

test('UI: attachments, duplicate prevention, new conversation and logout clear temporary state',async()=>{
  const h=await harness();try{
    await h.login();const file=new h.w.File(['notas'],'notas.txt',{type:'text/plain',lastModified:1});
    Object.defineProperty(h.el('file-input'),'files',{value:[file],configurable:true});h.el('file-input').dispatchEvent(new h.w.Event('change'));
    await until(()=>h.w.document.querySelector('.attachment-state')?.textContent.includes('pronto'));
    h.el('file-input').dispatchEvent(new h.w.Event('change'));await tick();assert.equal(h.w.document.querySelectorAll('.attachment').length,1);
    await h.send('Leia isto');const sent=JSON.parse(h.calls.find(x=>x.url.endsWith('/api/chat')).options.body);assert.deepEqual(sent.messages[0].file_ids,['file-test']);
    h.click('#new-chat');assert.equal(h.w.document.querySelectorAll('.message').length,0);assert.equal(h.el('welcome').hidden,false);assert.equal(h.el('chat-view').hidden,false);
    await h.send('Outra mensagem');h.click('#account-toggle');h.click('#logout');await until(()=>!h.el('login-view').hidden);
    assert.equal(h.w.document.querySelectorAll('.message').length,0);assert.equal(h.w.localStorage.length,0);
    assert.deepEqual(h.errors,[]);
  }finally{h.dom.window.close();}
});

test('UI: reset during pending response cannot restore old conversation',async()=>{
  const h=await harness();try{
    await h.login();h.state.slow=true;h.input('message-input','Antiga');h.el('composer').dispatchEvent(new h.w.Event('submit',{cancelable:true}));await until(()=>!h.el('stop-button').hidden);
    h.click('#new-chat');h.state.slow=false;await h.send('Nova');await tick();
    assert.equal(h.w.document.querySelectorAll('.message.user').length,1);assert.equal(h.w.document.querySelector('.user-text').textContent,'Nova');assert.equal(h.el('send-button').hidden,false);
    assert.deepEqual(h.errors,[]);
  }finally{h.dom.window.close();}
});
