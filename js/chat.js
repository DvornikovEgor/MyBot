// AI director chat: talks to /api/chat on our own server (the Gemini key never
// reaches the browser) and turns the answer into a music recipe for the composer.

import { describeRecipe, normaliseRecipe } from './recipe.js';

const $ = (id) => document.getElementById(id);

const FRIENDLY = {
  no_key: 'AI-дирижёр не настроен: сервер запущен без GEMINI_API_KEY. Генератор при этом работает — пользуйся панелью параметров.',
  network: 'Сервер не смог достучаться до Gemini API. Проверь интернет и доступ к generativelanguage.googleapis.com.',
  bad_key: 'Сервер принял ключ Gemini, но Google его отклонён. Проверь GEMINI_API_KEY.',
  quota: 'Квота Gemini API исчерпана. Попробуй позже.',
  timeout: 'Gemini отвечал слишком долго. Попробуй ещё раз.',
  blocked: 'Запрос не прошёл фильтр безопасности Gemini. Переформулируй его.',
};

const ERROR_TITLE = {
  no_key: 'Нет ключа API',
  network: 'Нет связи с Gemini',
  bad_key: 'Ключ отклонён',
  quota: 'Квота исчерпана',
  timeout: 'Таймаут',
  blocked: 'Отфильтровано',
};

let getContext = () => ({});
const history = [];   // [{ role, text }] — the conversation sent to the server
let busy = false;

export function initChat(options = {}) {
  getContext = options.getContext || (() => ({}));

  $('chatForm').addEventListener('submit', (e) => {
    e.preventDefault();
    send($('chatInput').value);
  });

  const input = $('chatInput');
  input.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey && !e.isComposing) {
      e.preventDefault();
      send(input.value);
    }
  });
  input.addEventListener('input', () => autoGrow(input));

  for (const chip of document.querySelectorAll('#chips .chip')) {
    chip.addEventListener('click', () => send(chip.dataset.prompt));
  }

  greet();
  checkHealth();
}

async function checkHealth() {
  const pill = $('aiStatus');
  try {
    const res = await fetch('/api/health', { headers: { Accept: 'application/json' } });
    const data = await res.json();
    const ai = data && data.ai ? data.ai : null;
    if (!ai) throw new Error('bad payload');
    if (ai.ready) {
      pill.className = 'ai-status ok';
      pill.textContent = ai.provider === 'fake' ? 'заглушка · без Gemini' : `${ai.model} · на связи`;
    } else {
      pill.className = 'ai-status off';
      pill.textContent = 'нужен GEMINI_API_KEY';
    }
  } catch {
    // Opened as a static file, or an old server without the API: generation still works.
    pill.className = 'ai-status err';
    pill.textContent = 'сервер недоступен';
    $('chatSend').disabled = true;
  }
}

function greet() {
  addMessage('bot', [
    'Привет! Я дирижёр этого генератора — опиши словами, что хочешь услышать,',
    'а я подберу стиль, лад, тональность, темп и гармонические прогрессии,',
    'и движок соберёт из этого трек.',
    'Например: «тёмный синтвейв про ночную поездку, ми миноре, 100 BPM».',
  ].join(' '));
}

// ---------------------------------------------------------------- messaging

async function send(rawText) {
  const text = (rawText || '').trim();
  if (!text || busy) return;

  $('chatInput').value = '';
  autoGrow($('chatInput'));
  addMessage('user', text);
  history.push({ role: 'user', text });

  setBusy(true);
  const typing = addTyping();

  try {
    const res = await fetch('/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ messages: history, current: safeContext() }),
    });

    const data = await res.json().catch(() => null);
    if (!res.ok || !data || data.ok === false) {
      throw Object.assign(
        new Error((data && data.error && data.error.message) || `HTTP ${res.status}`),
        { code: (data && data.error && data.error.code) || 'unknown' },
      );
    }

    typing.remove();
    const recipe = normaliseRecipe(data.recipe, getContext());
    history.push({ role: 'model', text: recipe.reply });
    addMessage('bot', recipe.reply);
    addRecipeCard(recipe, data.model);

    if (recipe.apply) {
      applyRecipe(recipe);
    } else {
      window.dispatchEvent(new CustomEvent('recipe:changed', { detail: null }));
    }
  } catch (err) {
    typing.remove();
    // Roll the user turn back so the next send keeps the conversation coherent.
    if (history[history.length - 1] && history[history.length - 1].text === text) history.pop();
    const code = err.code || 'unknown';
    const title = ERROR_TITLE[code] ? ERROR_TITLE[code] + '. ' : '';
    addMessage('bot', title + (FRIENDLY[code] || err.message), true);
  } finally {
    setBusy(false);
    $('chatInput').focus();
  }
}

function safeContext() {
  try {
    return getContext() || {};
  } catch {
    return {};
  }
}

function applyRecipe(recipe) {
  window.dispatchEvent(new CustomEvent('recipe:apply', { detail: recipe }));
}

// ---------------------------------------------------------------- rendering

function addMessage(role, text, isError = false) {
  const el = document.createElement('div');
  el.className = `msg ${role}${isError ? ' err' : ''}`;
  el.innerHTML = render(text);
  $('chatLog').appendChild(el);
  scrollLog();
  return el;
}

function addTyping() {
  const el = document.createElement('div');
  el.className = 'msg bot typing';
  el.textContent = '•••';
  $('chatLog').appendChild(el);
  scrollLog();
  return el;
}

function addRecipeCard(recipe, model) {
  const card = document.createElement('div');
  card.className = 'recipe-card';

  const title = document.createElement('h3');
  title.textContent = '🎼 ' + recipe.title;
  card.appendChild(title);

  const dl = document.createElement('dl');
  for (const [label, value] of describeRecipe(recipe)) {
    const dt = document.createElement('dt');
    dt.textContent = label;
    const dd = document.createElement('dd');
    dd.textContent = value;
    dl.append(dt, dd);
  }
  card.appendChild(dl);

  if (recipe.notes) {
    const notes = document.createElement('p');
    notes.className = 'notes';
    notes.textContent = recipe.notes;
    card.appendChild(notes);
  }

  const actions = document.createElement('div');
  actions.className = 'chips';
  actions.style.marginTop = '9px';

  if (!recipe.apply) {
    const build = document.createElement('button');
    build.className = 'chip';
    build.textContent = '▶ Собрать трек';
    build.addEventListener('click', () => applyRecipe(recipe));
    actions.appendChild(build);
  }

  const again = document.createElement('button');
  again.className = 'chip';
  again.textContent = '↻ Другой вариант';
  again.title = 'Тот же рецепт, новый сид';
  again.addEventListener('click', () => {
    applyRecipe({ ...recipe, seed: String(Math.floor(Math.random() * 1e6)) });
  });
  actions.appendChild(again);

  if (model) {
    const via = document.createElement('span');
    via.className = 'chip';
    via.style.cursor = 'default';
    via.textContent = model;
    actions.appendChild(via);
  }

  card.appendChild(actions);
  $('chatLog').appendChild(card);
  scrollLog();
}

/** Minimal inline markup: **bold** and `code`. Everything else is escaped. */
function render(text) {
  const esc = (s) => s.replace(/[&<>"']/g, (c) => (
    { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]
  ));
  return esc(text)
    .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
    .replace(/`([^`]+)`/g, '<code>$1</code>');
}

function scrollLog() {
  const log = $('chatLog');
  log.scrollTop = log.scrollHeight;
}

function setBusy(value) {
  busy = value;
  $('chatSend').disabled = value;
  for (const chip of document.querySelectorAll('#chips .chip')) chip.disabled = value;
}

function autoGrow(el) {
  el.style.height = 'auto';
  el.style.height = Math.min(el.scrollHeight, 140) + 'px';
}
