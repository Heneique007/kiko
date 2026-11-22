// Incremental SSE framing. Handles CR/LF/CRLF split across reads and multiline data.
export class SSEParser {
  constructor(onEvent) { this.onEvent = onEvent; this.buffer = ''; this.type = 'message'; this.parts = []; }
  line(line) {
    if (!line) {
      if (this.parts.length) this.onEvent(this.type, this.parts.join('\n'));
      this.type = 'message'; this.parts = []; return;
    }
    if (line.startsWith(':')) return;
    const index = line.indexOf(':');
    const field = index < 0 ? line : line.slice(0, index);
    let value = index < 0 ? '' : line.slice(index + 1);
    if (value.startsWith(' ')) value = value.slice(1);
    if (field === 'data') this.parts.push(value);
    if (field === 'event') this.type = value;
  }
  feed(text, final = false) {
    this.buffer += text;
    if (this.buffer.length > 1000000) throw new Error('Evento demasiado grande.');
    let match;
    while ((match = /\r\n|\n|\r(?!$)/.exec(this.buffer))) {
      this.line(this.buffer.slice(0, match.index)); this.buffer = this.buffer.slice(match.index + match[0].length);
    }
    if (final) {
      if (this.buffer.endsWith('\r')) { this.line(this.buffer.slice(0, -1)); this.buffer = ''; }
      if (this.buffer) this.line(this.buffer);
      this.buffer = ''; this.line('');
    }
  }
}
