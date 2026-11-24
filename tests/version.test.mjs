import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import vm from 'node:vm';
const source = readFileSync(new URL('../frontend/js/version.js', import.meta.url), 'utf8')
  .replace("import { config } from './config.js';", "const config = {apiBaseUrl:'https://api.example'};")
  .replace('export function setupVersion', 'function setupVersion');
const settle = () => new Promise(resolve => setImmediate(resolve));
function start({storage=new Map(), cacheNames=new Set(['kiko-static-v3','other']), api={version:'1.1.0',build:'source'}, published={version:'1.1.0',build:'source'}, draft=''}={}) {
  const events = new Map(), reloads = [], label = {}, input = {value:draft};
  const elements = {'app-version':label,'message-input':input,'login-view':{hidden:true},email:{value:''},password:{value:''},'new-chat':{addEventListener(){}}};
  const location = {href:'https://example.com/kiko/',protocol:'https:',hostname:'example.com',replace(url){reloads.push(url);}};
  const caches = {keys:async()=>[...cacheNames],delete:async name=>cacheNames.delete(name)};
  const state = {api,published};
  const context = {URL, AbortSignal, Date, location, history:{replaceState(){}}, window:{caches,addEventListener:(name,fn)=>events.set(name,fn)},
    caches, navigator:{onLine:true}, document:{baseURI:location.href,hidden:false,querySelector:({toString})=>({content:'source'}),getElementById:id=>elements[id],addEventListener(){}},
    localStorage:{getItem:k=>storage.get(k)??null,setItem:(k,v)=>storage.set(k,v)},
    fetch:async url=>({ok:true,json:async()=>String(url).includes('/api/version')?state.api:state.published}), setInterval(){} };
  context.document.querySelector = selector=>({content:selector.includes('kiko-build')?'source':'1.1.0'});
  vm.runInNewContext(source+'\nsetupVersion({busy:false,turns:[],attachments:{items:[]}});',context);
  return {state, storage, cacheNames, reloads, label, input, check:()=>events.get('focus')()};
}
test('manual version change clears only KIKO cache, reloads once, and preserves auth',async()=>{
  const app=start(); await settle(); app.storage.set('firebase-auth','persisted');
  app.state.api={version:'1.1.1',build:'source'}; app.check(); await settle();
  assert.equal(app.reloads.length,1); assert.deepEqual([...app.cacheNames],['other']); assert.equal(app.storage.get('firebase-auth'),'persisted');
  const restarted=start({storage:app.storage,api:app.state.api}); await settle();
  assert.equal(restarted.label.textContent,'1.1.1'); assert.equal(restarted.reloads.length,0);
  restarted.state.api=null; restarted.check(); await settle(); assert.equal(restarted.label.textContent,'1.1.1'); assert.equal(restarted.reloads.length,0);
});
test('draft defers reload; a different published build triggers only one retry',async()=>{
  const app=start({draft:'rascunho'}); await settle(); app.state.api={version:'1.1.1',build:'source'}; app.check(); await settle(); assert.equal(app.reloads.length,0);
  app.input.value=''; app.check(); await settle(); assert.equal(app.reloads.length,1);
  const newBuild={version:'1.1.0',build:'a'.repeat(24)};
  const old=start({published:newBuild}); await settle(); assert.equal(old.reloads.length,1);
  const again=start({storage:old.storage,published:newBuild}); await settle(); assert.equal(again.reloads.length,0);
});
