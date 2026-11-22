import { marked } from './vendor/marked.esm.js';
import DOMPurify from './vendor/purify.es.mjs';
export const $ = id => document.getElementById(id);
let toastTimer;
export function toast(text) { clearTimeout(toastTimer); $('toast').textContent = text; $('toast').hidden = false; toastTimer = setTimeout(() => { $('toast').hidden = true; }, 3200); }
export function messageError(id, text, info = false) { const el = $(id); el.textContent = text || ''; el.hidden = !text; el.classList.toggle('info', info); }
export function icon(name) { const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg'); const use = document.createElementNS(svg.namespaceURI, 'use'); use.setAttribute('href', `#i-${name}`); svg.append(use); return svg; }
export function markdown(target, text) {
  const rendered = marked.parse(text, { gfm: true, breaks: true, async: false });
  target.innerHTML = DOMPurify.sanitize(rendered, {
    ALLOWED_TAGS: ['p','br','strong','em','del','ul','ol','li','blockquote','pre','code','h1','h2','h3','h4','h5','h6','a','table','thead','tbody','tr','th','td','hr'],
    ALLOWED_ATTR: ['href','title','start'], ALLOW_DATA_ATTR: false,
  });
  for (const link of target.querySelectorAll('a')) {
    try { if (!['http:', 'https:', 'mailto:'].includes(new URL(link.getAttribute('href'), location.href).protocol)) link.removeAttribute('href'); }
    catch { link.removeAttribute('href'); }
    link.target = '_blank'; link.rel = 'noopener noreferrer';
  }
  for (const table of target.querySelectorAll('table')) { const wrap = document.createElement('div'); wrap.className = 'table-scroll'; table.replaceWith(wrap); wrap.append(table); }
}
export async function copy(text) {
  try { await navigator.clipboard.writeText(text); toast('Texto copiado.'); }
  catch {
    const input = document.createElement('textarea'); input.value = text; input.className = 'sr-only'; document.body.append(input); input.select();
    const success = document.execCommand('copy'); input.remove(); toast(success ? 'Texto copiado.' : 'Não foi possível copiar. Selecione o texto manualmente.');
  }
}
export function nearBottom() { const el = $('conversation'); return el.scrollHeight - el.clientHeight - el.scrollTop < 100; }
export function scrollBottom(force = false) { if (force || nearBottom()) $('conversation').scrollTop = $('conversation').scrollHeight; }
export function resizeInput() { const el = $('message-input'); el.style.height = 'auto'; el.style.height = `${Math.min(el.scrollHeight, window.visualViewport?.height < 500 ? 90 : 140)}px`; }
export function setupViewport() {
  const update = () => { const v = window.visualViewport; document.documentElement.style.setProperty('--app-height', `${v ? v.height : innerHeight}px`); resizeInput(); };
  window.visualViewport?.addEventListener('resize', update); window.addEventListener('resize', update); update();
  $('conversation').addEventListener('scroll', () => { $('scroll-bottom').hidden = nearBottom(); }, { passive: true });
  $('scroll-bottom').addEventListener('click', () => scrollBottom(true));
  const network = () => { $('network-banner').hidden = navigator.onLine; window.dispatchEvent(new Event('kiko-network')); };
  window.addEventListener('online', network); window.addEventListener('offline', network); network();
}
