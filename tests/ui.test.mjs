// Wiring smoke test: everything the UI reaches for must actually exist in the page.
// Catches the classic "renamed an id in HTML, forgot the JS" breakage.

import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';
import { test } from 'node:test';

const root = join(dirname(fileURLToPath(import.meta.url)), '..');
const read = (p) => readFileSync(join(root, p), 'utf8');

const html = read('index.html');
const css = read('css/style.css');
const idsIn = (src) => {
  const ids = new Set();
  for (const m of src.matchAll(/\$\('([^']+)'\)/g)) ids.add(m[1]);
  for (const m of src.matchAll(/getElementById\('([^']+)'\)/g)) ids.add(m[1]);
  return ids;
};

const htmlIds = new Set([...html.matchAll(/\bid="([^"]+)"/g)].map((m) => m[1]));

test('every element id used by app.js exists in index.html', () => {
  const missing = [...idsIn(read('js/app.js'))].filter((id) => !htmlIds.has(id));
  assert.deepEqual(missing, [], `missing ids: ${missing.join(', ')}`);
});

test('every element id used by chat.js exists in index.html', () => {
  const missing = [...idsIn(read('js/chat.js'))].filter((id) => !htmlIds.has(id));
  assert.deepEqual(missing, [], `missing ids: ${missing.join(', ')}`);
});

test('the chat panel is wired into the page', () => {
  for (const id of ['chatForm', 'chatInput', 'chatSend', 'chatLog', 'aiStatus', 'chips', 'aiBadge']) {
    assert.ok(htmlIds.has(id), `missing #${id}`);
  }
  assert.match(html, /<script type="module" src="js\/app\.js">/);
});

test('classes used by the chat code are styled', () => {
  for (const cls of ['chat-panel', 'chat-log', 'msg', 'msg user', 'msg bot', 'recipe-card', 'chip', 'ai-status', 'ai-badge']) {
    assert.ok(css.includes('.' + cls.split(' ').pop()), `no CSS for .${cls}`);
  }
});

test('the layout has room for the new column', () => {
  assert.match(css, /grid-template-columns:\s*320px minmax\(300px, 360px\) 1fr/);
  assert.match(css, /@media \(max-width: 980px\)/);
});
