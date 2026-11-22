import { $, icon, toast } from './ui.js';
import { uploadFile, request, friendly } from './api.js';

export class Attachments {
  constructor(onChange) { this.items = []; this.settings = null; this.onChange = onChange; }
  configure(data) {
    this.settings = data;
    $('file-input').accept = data.extensions.join(','); $('attach-button').disabled = false; $('file-limits').disabled = false;
    const l = data.limits;
    $('limits-content').textContent = `Até ${l.max_file_bytes / 1048576} MB por ficheiro e ${l.max_attachments} anexos por mensagem. Limite partilhado: ${l.max_total_bytes / 1048576} MB e ${l.max_files} ficheiros, com validade de ${l.file_ttl_hours} horas. Extração até ${l.max_doc_chars.toLocaleString('pt-PT')} caracteres por documento; contexto até ${l.max_context_chars.toLocaleString('pt-PT')} caracteres. Formatos: ${data.extensions.join(', ')}.`;
  }
  get uploading() { return this.items.some(item => item.state === 'uploading'); }
  get valid() { return this.items.filter(item => item.meta && item.state === 'ready'); }
  async add(files) {
    if (!this.settings) return;
    for (const file of files) {
      if (this.items.length >= this.settings.limits.max_attachments) { toast('Limite de anexos por mensagem atingido.'); break; }
      const signature = `${file.name}:${file.size}:${file.lastModified}`;
      if (this.items.some(item => item.signature === signature)) { toast('Este ficheiro já está anexado.'); continue; }
      const ext = '.' + file.name.split('.').pop().toLowerCase();
      if (!this.settings.extensions.includes(ext)) { toast(`Formato não suportado: ${ext}`); continue; }
      if (!file.size || file.size > this.settings.limits.max_file_bytes) { toast(`O ficheiro deve ter entre 1 byte e ${this.settings.limits.max_file_bytes / 1048576} MB.`); continue; }
      const preview = /\.(png|jpe?g|webp|gif)$/i.test(file.name) ? URL.createObjectURL(file) : null;
      const item = { file, signature, preview, name: file.name, state: 'uploading', progress: 0, controller: new AbortController() };
      this.items.push(item); this.render();
      uploadFile(file, item.controller.signal, progress => { item.progress = progress; if (this.items.includes(item)) this.render(); }).then(meta => {
        if (!this.items.includes(item)) { request(`/api/files/${meta.id}`, { method: 'DELETE' }).catch(() => {}); return; }
        item.meta = meta; item.state = 'ready'; item.file = null;
        if (meta.truncated) toast('O documento foi limitado ao máximo de texto configurado.'); this.render();
      }).catch(error => {
        if (!this.items.includes(item)) return;
        item.state = 'error'; item.error = friendly(error); item.file = null; this.render();
      });
    }
  }
  remove(item, deleteRemote = true) {
    item.controller.abort(); this.items = this.items.filter(i => i !== item);
    if (item.preview) URL.revokeObjectURL(item.preview);
    if (deleteRemote && item.meta) request(`/api/files/${item.meta.id}`, { method: 'DELETE' }).catch(() => {});
    this.render();
  }
  take() { const result = this.valid.map(item => item.meta); for (const item of [...this.items]) this.remove(item, false); return result; }
  clear() { for (const item of [...this.items]) this.remove(item); }
  render() {
    $('attachment-list').replaceChildren();
    for (const item of this.items) {
      const el = document.createElement('div'); el.className = `attachment ${item.state}`;
      if (item.preview) { const image = document.createElement('img'); image.src = item.preview; image.alt = ''; el.append(image); }
      else el.append(icon('file'));
      const info = document.createElement('div'); info.className = 'attachment-info';
      const name = document.createElement('span'); name.className = 'attachment-name'; name.textContent = item.name; name.title = item.name;
      const status = document.createElement('span'); status.className = 'attachment-state'; status.setAttribute('role', 'status');
      status.textContent = item.state === 'uploading' ? (item.progress === 100 ? 'A analisar…' : `A enviar… ${item.progress}%`) : item.state === 'error' ? item.error : `${Math.ceil(item.meta.bytes / 1024)} KB · pronto${item.meta.truncated ? ' · texto limitado' : ''}`;
      info.append(name, status); const remove = document.createElement('button'); remove.type = 'button'; remove.className = 'icon-button'; remove.setAttribute('aria-label', `Remover ${item.name}`); remove.append(icon('close')); remove.addEventListener('click', () => this.remove(item));
      el.append(info, remove); $('attachment-list').append(el);
    }
    this.onChange();
  }
}
