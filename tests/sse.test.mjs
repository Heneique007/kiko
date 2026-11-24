import test from 'node:test';
import assert from 'node:assert/strict';
import { SSEParser } from '../frontend/js/sse.js';
test('SSE: every UTF-8 byte boundary, Unicode, CRLF, multiline, comments', () => {
  const source = ': heartbeat\r\nevent: delta\r\ndata: {"text":\r\ndata: "Olá 🧡"}\r\n\r\nevent: done\ndata: {}\n\n';
  const bytes = new TextEncoder().encode(source);
  for (let size = 1; size <= bytes.length; size++) {
    const result = []; const parser = new SSEParser((type, value) => result.push([type, JSON.parse(value)])); const decoder = new TextDecoder();
    for (let i = 0; i < bytes.length; i += size) parser.feed(decoder.decode(bytes.slice(i, i + size), { stream: true }));
    parser.feed(decoder.decode(), true);
    assert.deepEqual(result, [['delta', { text: 'Olá 🧡' }], ['done', {}]]);
  }
});
test('SSE: final unterminated event and bare CR', () => {
  const result = []; const p = new SSEParser((type, data) => result.push([type, data]));
  p.feed('event: delta\rdata: olá\r\r'); p.feed('event: done\ndata: {}', true);
  assert.deepEqual(result, [['delta','olá'],['done','{}']]);
});
test('SSE: rejects oversized frame', () => { const p = new SSEParser(() => {}); assert.throws(() => p.feed('a'.repeat(1000001))); });
