import { $, copy, icon, markdown, messageError, nearBottom, resizeInput, scrollBottom } from './ui.js';
import { streamChat, request, friendly } from './api.js';
import { Attachments } from './files.js';

const modes = new Set(['learn', 'think', 'quick']);
export class Chat {
  constructor() {
    this.mode = 'think'; this.turns = []; this.busy = false; this.ready = false; this.generation = 0;
    this.attachments = new Attachments(() => this.update());
    $('composer').addEventListener('submit', event => { event.preventDefault(); this.send(); });
    $('message-input').addEventListener('input', () => { resizeInput(); this.update(); });
    $('message-input').addEventListener('keydown', event => {
      if (event.key === 'Enter' && !event.shiftKey && !event.isComposing && matchMedia('(pointer: fine)').matches) { event.preventDefault(); this.send(); }
    });
    $('stop-button').addEventListener('click', () => this.stop());
    $('new-chat').addEventListener('click', () => { this.reset(); $('message-input').focus(); });
    for (const button of document.querySelectorAll('[data-mode]')) button.addEventListener('click', () => this.selectMode(button.dataset.mode));
    $('attach-button').addEventListener('click', () => $('file-input').click());
    $('file-input').addEventListener('change', () => { this.attachments.add([...$('file-input').files]); $('file-input').value = ''; });
    window.addEventListener('kiko-network', () => this.update());
    this.update();
  }
  configure(me) { this.ready = true; this.attachments.configure(me); $('message-input').maxLength = me.limits.max_message_chars ?? 160000; this.update(); }
  selectMode(mode) { if (!modes.has(mode)) return; this.mode = mode; for (const b of document.querySelectorAll('[data-mode]')) b.setAttribute('aria-pressed', String(b.dataset.mode === mode)); }
  update() {
    $('send-button').disabled = !this.ready || this.busy || this.attachments.uploading || !navigator.onLine || (!$('message-input').value.trim() && !this.attachments.valid.length) || this.attachments.items.some(item => item.state === 'error');
    $('send-button').hidden = this.busy; $('stop-button').hidden = !this.busy; $('composer').setAttribute('aria-busy', String(this.busy));
    for (const button of document.querySelectorAll('.regenerate-button')) button.disabled = this.busy;
  }
  stop() { this.controller?.abort(new DOMException('Interrompido pelo utilizador.', 'AbortError')); }
  reset() {
    this.generation++; this.stop(); this.busy = false;
    const ids = new Set(this.turns.flatMap(turn => turn.files.map(file => file.id)));
    for (const id of ids) request(`/api/files/${id}`, { method: 'DELETE' }).catch(() => {});
    this.turns = []; this.attachments.clear(); $('messages').replaceChildren(); $('welcome').hidden = false; $('message-input').value = ''; messageError('chat-error', ''); resizeInput(); this.update();
  }
  async send() {
    this.update(); if ($('send-button').disabled) return;
    const content = $('message-input').value.trim(); const files = this.attachments.take();
    $('message-input').value = ''; resizeInput(); messageError('chat-error', ''); $('welcome').hidden = true;
    const turn = { content, files, answer: '', mode: this.mode, state: 'pending' }; this.turns.push(turn);
    const user = document.createElement('article'); user.className = 'message user'; user.setAttribute('aria-label', 'A sua mensagem');
    const text = document.createElement('div'); text.className = 'user-text'; text.textContent = content; user.append(text);
    if (files.length) { const list = document.createElement('div'); list.className = 'message-files'; for (const file of files) { const item = document.createElement('span'); item.className = 'message-file'; item.textContent = file.filename; list.append(item); } user.append(list); }
    $('messages').append(user); this.makeAssistant(turn); scrollBottom(true); await this.generate(turn);
  }
  makeAssistant(turn) {
    const el = document.createElement('article'); el.className = 'message assistant'; el.setAttribute('aria-label', 'Resposta da KIKO');
    const heading = document.createElement('div'); heading.className = 'message-heading';
    const name = document.createElement('span'); name.textContent = 'KIKO';
    turn.modeEl = document.createElement('span'); turn.modeEl.className = 'message-mode'; turn.modeEl.textContent = turn.mode[0].toUpperCase() + turn.mode.slice(1); heading.append(name, turn.modeEl);
    turn.body = document.createElement('div'); turn.body.className = 'message-content';
    turn.status = document.createElement('div'); turn.status.className = 'message-status'; turn.status.setAttribute('role', 'status');
    turn.actions = document.createElement('div'); turn.actions.className = 'message-actions';
    const copyButton = document.createElement('button'); copyButton.type = 'button'; copyButton.append(icon('copy'), document.createTextNode('Copiar')); copyButton.addEventListener('click', () => copy(turn.answer));
    const regenerate = document.createElement('button'); regenerate.type = 'button'; regenerate.className = 'regenerate-button'; regenerate.append(icon('refresh'), document.createTextNode('Tentar novamente')); regenerate.addEventListener('click', () => { if (this.turns.at(-1) === turn && !this.busy) { turn.mode = this.mode; this.generate(turn); } });
    turn.copyButton = copyButton; turn.regenerate = regenerate; turn.actions.append(copyButton, regenerate); el.append(heading, turn.body, turn.status, turn.actions); $('messages').append(el); turn.el = el;
  }
  history(turn) {
    const messages = [];
    for (const previous of this.turns) {
      if (previous === turn) break;
      // Empty failed/interrupted turns are visible but do not create malformed context.
      if (!previous.answer) continue;
      messages.push({ role: 'user', content: previous.content, file_ids: previous.files.map(f => f.id) }, { role: 'assistant', content: previous.answer });
    }
    messages.push({ role: 'user', content: turn.content, file_ids: turn.files.map(f => f.id) }); return messages;
  }
  async generate(turn) {
    if (this.busy || !this.ready) return;
    if (turn.files.some(file => file.expires_at * 1000 <= Date.now())) { messageError('chat-error', 'Um anexo expirou. Inicie uma nova conversa e volte a anexá-lo.'); return; }
    const seq = ++this.generation; const controller = new AbortController(); this.controller = controller; this.busy = true;
    turn.answer = ''; turn.state = 'pending'; turn.body.replaceChildren(); turn.actions.hidden = true; turn.status.classList.remove('error'); turn.status.textContent = 'A preparar a resposta…'; turn.el.classList.add('generating');
    turn.modeEl.textContent = turn.mode[0].toUpperCase() + turn.mode.slice(1); this.update();
    for (const old of this.turns) old.regenerate.hidden = old !== turn;
    let frame = null;
    const draw = () => { frame = null; if (seq !== this.generation) return; const follow = nearBottom(); markdown(turn.body, turn.answer); if (follow) scrollBottom(true); };
    try {
      await streamChat({ mode: turn.mode, messages: this.history(turn), stream: true }, controller.signal, (type, data) => {
        if (seq !== this.generation) return;
        if (type === 'meta') { turn.nativeStream = data.streaming; turn.status.textContent = data.streaming ? 'A responder…' : 'Resposta completa · streaming nativo indisponível'; }
        if (type === 'delta') { turn.answer += data.text; if (turn.answer.length > 160000) throw new Error('A resposta excedeu o limite de apresentação.'); if (frame === null) frame = requestAnimationFrame(draw); }
      });
      turn.state = 'complete'; turn.status.textContent = '';
    } catch (error) {
      turn.state = error.name === 'AbortError' ? 'interrupted' : 'error';
      turn.status.textContent = error.name === 'AbortError' ? 'Geração interrompida. O texto recebido foi preservado.' : friendly(error);
      turn.status.classList.toggle('error', turn.state === 'error');
    } finally {
      if (frame !== null) cancelAnimationFrame(frame);
      if (seq === this.generation) {
        draw(); turn.el.classList.remove('generating'); turn.actions.hidden = false; turn.copyButton.hidden = !turn.answer;
        turn.regenerate.lastChild.textContent = turn.state === 'complete' ? 'Regenerar' : 'Tentar novamente'; this.busy = false; this.controller = null; this.update();
        if (turn.state === 'complete') turn.status.textContent = turn.nativeStream === false ? 'Resposta concluída · sem streaming nativo.' : 'Resposta concluída.';
      }
    }
  }
}
