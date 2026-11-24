import { config } from './config.js';
import { token } from './firebase.js';
import { SSEParser } from './sse.js';
const base = () => config.apiBaseUrl.replace(/\/$/, '');

export function friendly(error) {
  if (!navigator.onLine) return 'Sem ligação à internet. Volte a tentar quando estiver online.';
  if (error.name === 'TimeoutError') return 'O pedido excedeu o tempo de espera. Tente novamente.';
  if (error.status === 401) return 'A sessão expirou. Feche este separador e abra a KIKO novamente.';
  if (error.status === 403) return 'Esta conta não está autorizada. Contacte o administrador.';
  if (error instanceof TypeError) return 'Não foi possível contactar o servidor. Verifique a ligação e a configuração da API.';
  return error.message || 'Não foi possível concluir o pedido.';
}

async function failure(response) {
  let data; try { data = await response.json(); } catch { /* A proxy may return HTML. */ }
  const error = new Error(data?.error?.message || `O servidor não respondeu corretamente (${response.status}).`);
  error.status = response.status; throw error;
}

export async function request(path, options = {}) {
  const controller = new AbortController();
  const parent = options.signal;
  const abort = () => controller.abort(parent.reason);
  if (parent?.aborted) abort(); else parent?.addEventListener('abort', abort, { once: true });
  const timer = setTimeout(() => controller.abort(new DOMException('Tempo de espera excedido.', 'TimeoutError')), 240000);
  try {
    const bearer = await token();
    const headers = { Authorization: `Bearer ${bearer}`, ...options.headers };
    const response = await fetch(base() + path, { ...options, signal: controller.signal, headers, cache: 'no-store', credentials: 'omit' });
    if (!response.ok) await failure(response);
    return await response.json();
  } catch (error) { if (controller.signal.aborted) throw controller.signal.reason; throw error; }
  finally { clearTimeout(timer); parent?.removeEventListener('abort', abort); }
}

export async function streamChat(payload, signal, onEvent) {
  const controller = new AbortController();
  const abort = () => controller.abort(signal.reason);
  if (signal.aborted) abort(); else signal.addEventListener('abort', abort, { once: true });
  const timer = setTimeout(() => controller.abort(new DOMException('Tempo de espera excedido.', 'TimeoutError')), 240000);
  let reader;
  try {
    const bearer = await token();
    const response = await fetch(base() + '/api/chat', { method: 'POST',
      headers: { Authorization: `Bearer ${bearer}`, 'Content-Type': 'application/json' },
      body: JSON.stringify(payload), signal: controller.signal, cache: 'no-store', credentials: 'omit' });
    if (!response.ok) await failure(response);
    if (!response.headers.get('content-type')?.includes('text/event-stream') || !response.body) throw new Error('O servidor não devolveu streaming compatível.');
    reader = response.body.getReader();
    let done = false;
    const decoder = new TextDecoder('utf-8');
    const parser = new SSEParser((type, raw) => {
      let data; try { data = JSON.parse(raw); } catch { throw new Error('Resposta de streaming inválida.'); }
      if (type === 'error') throw new Error(data.message || 'A geração foi interrompida.');
      if (type === 'done') done = true;
      if (type === 'delta' && typeof data.text !== 'string') throw new Error('Resposta de streaming inválida.');
      onEvent(type, data);
    });
    while (!done) {
      const chunk = await reader.read();
      parser.feed(decoder.decode(chunk.value || new Uint8Array(), { stream: !chunk.done }), chunk.done);
      if (chunk.done) break;
    }
    if (!done) throw new Error('A ligação foi interrompida antes de concluir a resposta. Pode tentar novamente.');
  } catch (error) { if (controller.signal.aborted) throw controller.signal.reason; throw error; }
  finally { clearTimeout(timer); signal.removeEventListener('abort', abort); if (reader) { try { await reader.cancel(); } catch {} reader.releaseLock(); } controller.abort(); }
}

export async function uploadFile(file, signal, onProgress) {
  const bearer = await token();
  signal.throwIfAborted();
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    const abort = () => xhr.abort();
    const cleanup = () => signal.removeEventListener('abort', abort);
    xhr.open('POST', base() + '/api/files'); xhr.setRequestHeader('Authorization', `Bearer ${bearer}`); xhr.timeout = 300000;
    xhr.upload.onprogress = event => { if (event.lengthComputable) onProgress(Math.round(event.loaded / event.total * 100)); };
    xhr.onload = () => { cleanup(); let data; try { data = JSON.parse(xhr.responseText); } catch {} if (xhr.status >= 200 && xhr.status < 300 && data?.id) resolve(data); else { const error = new Error(data?.error?.message || 'Falha no envio do anexo.'); error.status = xhr.status; reject(error); } };
    xhr.onerror = () => { cleanup(); reject(new TypeError('Falha no upload.')); };
    xhr.ontimeout = () => { cleanup(); reject(new DOMException('O upload excedeu o tempo de espera.', 'TimeoutError')); };
    xhr.onabort = () => { cleanup(); reject(new DOMException('Upload cancelado.', 'AbortError')); };
    signal.addEventListener('abort', abort, { once: true });
    const body = new FormData(); body.append('file', file); xhr.send(body);
  });
}
