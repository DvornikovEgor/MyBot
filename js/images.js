// MyBot · ИИ генератор картинок (Flux через Pollinations.ai, бесплатно, без ключей).

const $ = (id) => document.getElementById(id);

const API_BASE = 'https://image.pollinations.ai/prompt';
const HISTORY_KEY = 'mybot_images_v1';
const HISTORY_LIMIT = 40;

// Суффиксы стилей (на английском — так нейросеть понимает лучше).
const STYLES = {
  none: '',
  photo: ', ultra realistic photograph, 85mm lens, dramatic lighting, sharp focus, highly detailed, 8k',
  cinematic: ', cinematic film still, dramatic lighting, shallow depth of field, film grain, epic composition',
  anime: ', beautiful anime art, vibrant colors, detailed, studio quality, clean lines',
  cyberpunk: ', cyberpunk style, neon lights, futuristic, rain reflections, cinematic, highly detailed',
  fantasy: ', epic fantasy digital art, intricate details, dramatic lighting, magical atmosphere, artstation',
  scifi: ', science fiction concept art, futuristic, detailed spacecraft, dramatic space lighting',
  watercolor: ', delicate watercolor painting, soft brush strokes, paper texture, artistic',
  oil: ', classical oil painting, textured canvas, rich colors, museum quality',
  '3d': ', 3d render, octane render, soft studio lighting, cute, high quality, detailed',
  pixel: ', pixel art, 16-bit style, detailed sprites, vibrant palette, retro game',
  comic: ', comic book style, bold outlines, vibrant colors, dynamic composition',
  logo: ', minimalist flat design, clean vector style, simple shapes, elegant',
};

const STYLE_NAMES = {
  none: 'без стиля', photo: 'Фотореализм', cinematic: 'Кинокадр', anime: 'Аниме',
  cyberpunk: 'Киберпанк', fantasy: 'Фэнтези', scifi: 'Sci-Fi', watercolor: 'Акварель',
  oil: 'Масло', '3d': '3D-рендер', pixel: 'Пиксель-арт', comic: 'Комикс', logo: 'Минимализм',
};

const MODEL_NAMES = { flux: 'Flux', turbo: 'Turbo' };

const IDEAS = [
  'Замок на летающем острове в облаках на закате',
  'Космический кот в скафандре среди звёзд',
  'Уютное кафе в дождливом Токио ночью, неон',
  'Дракон над снежными горами, эпично',
  'Подводный город с китами и кораллами',
  'Робот-бариста варит кофе в стиле стимпанк',
  'Волшебный лес со светящимися грибами',
  'Портрет эльфийки с серебряными волосами',
  'Марсианская колония, закат, роверы',
  'Пряничный домик в зимнем лесу',
  'Самурай на фоне цветущей сакуры',
  'Летающий автомобиль над ночным городом',
  'Древний храм в джунглях, лучи солнца',
  'Милая лиса в осеннем лесу, акварель',
  'Киберпанк-рынок в дождливую ночь',
  'Замок из мороженого в космосе',
  'Викингский корабль в штормовом море',
  'Оазис в пустыне с пальмами и фламинго',
];

const CHIP_IDEAS = [
  '🦊 Лиса в лесу', '🏰 Летающий замок', '🐉 Дракон',
  '🌃 Неоновый город', '🚀 Космос', '🌸 Сакура',
  '🤖 Робот', '🌊 Океан', '🏔️ Горы', '🎃 Хэллоуин',
];

const state = {
  items: [],        // { id, prompt, fullPrompt, url, seed, model, style, size, time }
  selectedId: null,
  generating: false,
  timer: null,
  startTime: 0,
};

// =====================================================================
// Init
// =====================================================================

function init() {
  $('seed').value = String(Math.floor(Math.random() * 999999));
  $('count').addEventListener('input', () => {
    $('countVal').textContent = $('count').value;
  });
  $('prompt').addEventListener('input', () => {
    $('charCount').textContent = $('prompt').value.length;
    updateMeta();
  });
  $('prompt').addEventListener('keydown', (e) => {
    if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') generate();
  });
  ['style', 'model', 'size'].forEach((id) => $(id).addEventListener('change', updateMeta));

  $('generate').addEventListener('click', generate);
  $('randomSeed').addEventListener('click', () => {
    $('seed').value = String(Math.floor(Math.random() * 999999));
  });
  $('surprise').addEventListener('click', () => {
    $('prompt').value = IDEAS[Math.floor(Math.random() * IDEAS.length)];
    $('charCount').textContent = $('prompt').value.length;
    updateMeta();
    generate();
  });
  $('clearPrompt').addEventListener('click', () => {
    $('prompt').value = '';
    $('charCount').textContent = '0';
    updateMeta();
    $('prompt').focus();
  });

  // chips
  CHIP_IDEAS.forEach((label) => {
    const b = document.createElement('button');
    b.className = 'chip';
    b.textContent = label;
    b.addEventListener('click', () => {
      $('prompt').value = label.replace(/^[^\s]+\s/, '');
      $('charCount').textContent = $('prompt').value.length;
      updateMeta();
      generate();
    });
    $('chips').appendChild(b);
  });

  $('download').addEventListener('click', () => downloadItem(selected()));
  $('downloadAll').addEventListener('click', downloadAll);
  $('openFull').addEventListener('click', () => openViewer(selected()));
  $('preview').addEventListener('click', () => openViewer(selected()));
  $('copyLink').addEventListener('click', copyLink);
  $('reuse').addEventListener('click', reuseSelected);
  $('clearHistory').addEventListener('click', clearHistory);

  // viewer
  $('viewerClose').addEventListener('click', closeViewer);
  $('viewer').addEventListener('click', (e) => {
    if (e.target === $('viewer')) closeViewer();
  });
  $('viewerPrev').addEventListener('click', (e) => { e.stopPropagation(); stepViewer(-1); });
  $('viewerNext').addEventListener('click', (e) => { e.stopPropagation(); stepViewer(1); });
  window.addEventListener('keydown', (e) => {
    if (!$('viewer').hidden) {
      if (e.key === 'Escape') closeViewer();
      if (e.key === 'ArrowLeft') stepViewer(-1);
      if (e.key === 'ArrowRight') stepViewer(1);
    }
  });

  loadHistory();
  renderGallery();
  updateMeta();

  // Параметры из URL: ?prompt=...&style=...&seed=...
  const params = new URLSearchParams(location.search);
  if (params.get('prompt')) {
    $('prompt').value = params.get('prompt');
    $('charCount').textContent = $('prompt').value.length;
  }
  if (params.get('style') && STYLES[params.get('style')] !== undefined) $('style').value = params.get('style');
  if (params.get('model') && MODEL_NAMES[params.get('model')]) $('model').value = params.get('model');
  if (params.get('size') && /^\d+x\d+$/.test(params.get('size'))) {
    const sel = $('size');
    if (![...sel.options].some((o) => o.value === params.get('size'))) {
      const o = document.createElement('option');
      o.value = params.get('size');
      o.textContent = `📐 ${params.get('size')}`;
      sel.appendChild(o);
    }
    sel.value = params.get('size');
  }
  if (params.get('seed')) $('seed').value = params.get('seed');
  updateMeta();
  if (params.get('prompt')) generate();
}

function selected() {
  return state.items.find((i) => i.id === state.selectedId) || null;
}

// =====================================================================
// URL builder
// =====================================================================

function buildUrl(fullPrompt, w, h, seed, model) {
  const p = new URLSearchParams({
    width: w,
    height: h,
    seed: String(seed),
    model,
    nologo: 'true',
  });
  if ($('enhance').checked) p.set('enhance', 'true');
  if ($('private').checked) p.set('private', 'true');
  return `${API_BASE}/${encodeURIComponent(fullPrompt)}?${p.toString()}`;
}

function currentSettings() {
  const prompt = $('prompt').value.trim();
  const style = $('style').value;
  const fullPrompt = prompt + (STYLES[style] || '');
  const [w, h] = $('size').value.split('x').map(Number);
  const model = $('model').value;
  const baseSeed = parseInt($('seed').value, 10);
  const seed = Number.isFinite(baseSeed) ? Math.abs(baseSeed) % 1000000 : Math.floor(Math.random() * 999999);
  const count = parseInt($('count').value, 10) || 1;
  return { prompt, style, fullPrompt, w, h, model, seed, count };
}

function updateMeta() {
  const { prompt, style, w, h, model } = currentSettings();
  $('meta').textContent = prompt
    ? `${STYLE_NAMES[style]} · ${MODEL_NAMES[model]} · ${w}×${h}`
    : 'Опишите картинку и нажмите «Сгенерировать».';
  $('fullPrompt').textContent = prompt ? '→ ' + prompt + (STYLES[style] || '') : '';
}

// =====================================================================
// Generation
// =====================================================================

async function generate() {
  if (state.generating) return;
  const s = currentSettings();
  if (!s.prompt) {
    toast('Сначала опишите картинку ✨');
    $('prompt').focus();
    return;
  }

  state.generating = true;
  $('generate').classList.add('busy');
  $('generate').disabled = true;
  setStatus(`Генерирую ${s.count} ${plural(s.count, 'вариант', 'варианта', 'вариантов')}…`);
  startLoader();

  const jobs = [];
  for (let k = 0; k < s.count; k++) {
    const seed = s.seed + k;
    const url = buildUrl(s.fullPrompt, s.w, s.h, seed, s.model);
    jobs.push({ prompt: s.prompt, fullPrompt: s.fullPrompt, url, seed, model: s.model, style: s.style, size: `${s.w}x${s.h}`, index: k });
  }

  // Показываем скелетоны в галерее сразу
  const placeholders = jobs.map((j) => addPlaceholder(j));

  let done = 0;
  let firstOk = null;

  await Promise.all(jobs.map(async (job, k) => {
    try {
      await preloadImage(job.url);
      const item = { ...job, id: Date.now() + '-' + k + '-' + job.seed, time: Date.now() };
      delete item.index;
      replacePlaceholder(placeholders[k], item);
      if (!firstOk) firstOk = item;
    } catch (err) {
      markPlaceholderError(placeholders[k], job);
      console.error('Generate failed:', job.url, err);
    } finally {
      done++;
      setStatus(`Готово ${done} из ${jobs.length}…`);
    }
  }));

  stopLoader();

  if (firstOk) {
    selectItem(firstOk.id);
    setStatus(`Готово: ${done} из ${jobs.length}. Клик по картинке — просмотр.`);
    // следующий сид — чтобы повторы не дублировались
    $('seed').value = String(s.seed + s.count);
  } else {
    setStatus('Не получилось сгенерировать. Проверьте интернет и попробуйте ещё раз.');
    toast('Ошибка генерации 😢 Попробуйте ещё раз');
  }

  state.generating = false;
  $('generate').classList.remove('busy');
  $('generate').disabled = false;
}

function preloadImage(url) {
  return new Promise((resolve, reject) => {
    const img = new Image();
    img.crossOrigin = 'anonymous';
    const timeout = setTimeout(() => reject(new Error('timeout')), 180000);
    img.onload = () => { clearTimeout(timeout); resolve(); };
    img.onerror = () => { clearTimeout(timeout); reject(new Error('load error')); };
    img.src = url;
  });
}

// =====================================================================
// Gallery + history
// =====================================================================

function addPlaceholder(job) {
  $('galleryEmpty')?.remove();
  const el = document.createElement('div');
  el.className = 'g-item loading';
  el.innerHTML = '<div class="g-spin">рисую…</div>';
  $('gallery').prepend(el);
  updateGalleryCount();
  return el;
}

function replacePlaceholder(el, item) {
  state.items.unshift(item);
  trimHistory();
  saveHistory();
  el.classList.remove('loading');
  el.innerHTML = '';
  el.dataset.id = item.id;
  const img = document.createElement('img');
  img.src = item.url;
  img.alt = item.prompt;
  img.loading = 'lazy';
  el.appendChild(img);
  const ov = document.createElement('div');
  ov.className = 'g-overlay';
  ov.innerHTML = '<button title="Скачать">⬇</button><button title="Промпт">↻</button>';
  const [dlBtn, reBtn] = ov.querySelectorAll('button');
  dlBtn.addEventListener('click', (e) => { e.stopPropagation(); downloadItem(item); });
  reBtn.addEventListener('click', (e) => { e.stopPropagation(); reuseItem(item); });
  el.appendChild(ov);
  el.addEventListener('click', () => selectItem(item.id));
  updateGalleryCount();
  $('clearHistory').disabled = false;
  $('downloadAll').disabled = false;
}

function markPlaceholderError(el, job) {
  el.classList.remove('loading');
  el.innerHTML = '<div class="g-spin">⚠️ ошибка</div>';
  el.title = job.prompt;
  el.style.cursor = 'default';
  setTimeout(() => {
    el.style.opacity = '0.4';
  }, 100);
  updateGalleryCount();
}

function renderGallery() {
  const g = $('gallery');
  g.innerHTML = '';
  if (state.items.length === 0) {
    g.innerHTML = '<p id="galleryEmpty" class="gallery-empty">Пока пусто — сгенерируйте первую картинку ✨</p>';
  } else {
    // восстанавливаем элементы из истории (новые сверху)
    [...state.items].forEach((item) => {
      const el = document.createElement('div');
      el.className = 'g-item' + (item.id === state.selectedId ? ' selected' : '');
      el.dataset.id = item.id;
      const img = document.createElement('img');
      img.src = item.url;
      img.alt = item.prompt;
      img.loading = 'lazy';
      el.appendChild(img);
      const ov = document.createElement('div');
      ov.className = 'g-overlay';
      ov.innerHTML = '<button title="Скачать">⬇</button><button title="Промпт">↻</button>';
      const [dlBtn, reBtn] = ov.querySelectorAll('button');
      dlBtn.addEventListener('click', (e) => { e.stopPropagation(); downloadItem(item); });
      reBtn.addEventListener('click', (e) => { e.stopPropagation(); reuseItem(item); });
      el.appendChild(ov);
      el.addEventListener('click', () => selectItem(item.id));
      g.appendChild(el);
    });
  }
  updateGalleryCount();
  const has = state.items.length > 0;
  $('clearHistory').disabled = !has;
  $('downloadAll').disabled = !has;
  if (has && !selected()) selectItem(state.items[0].id, true);
  else if (!has) clearPreview();
}

function updateGalleryCount() {
  $('galleryCount').textContent = state.items.length;
}

function selectItem(id, silent) {
  state.selectedId = id;
  const item = selected();
  document.querySelectorAll('.g-item').forEach((el) => {
    el.classList.toggle('selected', el.dataset.id === id);
  });
  if (!item) { clearPreview(); return; }
  $('previewWrap').classList.remove('empty');
  $('previewEmpty').hidden = true;
  const prev = $('preview');
  prev.hidden = false;
  prev.src = item.url;
  prev.alt = item.prompt;
  $('previewCaption').textContent = `${item.prompt} · ${STYLE_NAMES[item.style]} · seed ${item.seed}`;
  $('openFull').disabled = false;
  $('download').disabled = false;
  $('copyLink').disabled = false;
  $('reuse').disabled = false;
  if (!silent) saveHistory();
}

function clearPreview() {
  $('previewWrap').classList.add('empty');
  $('previewEmpty').hidden = false;
  $('preview').hidden = true;
  $('preview').removeAttribute('src');
  $('previewCaption').textContent = '—';
  $('openFull').disabled = true;
  $('download').disabled = true;
  $('copyLink').disabled = true;
  $('reuse').disabled = true;
}

function trimHistory() {
  if (state.items.length > HISTORY_LIMIT) {
    state.items.length = HISTORY_LIMIT;
  }
}

function saveHistory() {
  try {
    localStorage.setItem(HISTORY_KEY, JSON.stringify({
      items: state.items.slice(0, HISTORY_LIMIT),
      selectedId: state.selectedId,
    }));
  } catch { /* переполнено — игнорируем */ }
}

function loadHistory() {
  try {
    const raw = localStorage.getItem(HISTORY_KEY);
    if (!raw) return;
    const data = JSON.parse(raw);
    if (Array.isArray(data.items)) state.items = data.items;
    if (data.selectedId) state.selectedId = data.selectedId;
  } catch { /* битые данные — начинаем с чистого */ }
}

function clearHistory() {
  state.items = [];
  state.selectedId = null;
  saveHistory();
  renderGallery();
  toast('Галерея очищена');
}

// =====================================================================
// Actions
// =====================================================================

async function downloadItem(item) {
  if (!item) return;
  toast('Скачиваю…');
  try {
    const res = await fetch(item.url);
    if (!res.ok) throw new Error('http ' + res.status);
    const blob = await res.blob();
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = `mybot-${item.seed}.jpg`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(a.href), 5000);
    toast('Сохранено ✅');
  } catch {
    // запасной вариант — открыть в новой вкладке
    window.open(item.url, '_blank');
    toast('Открыл картинку в новой вкладке');
  }
}

async function downloadAll() {
  const items = [...document.querySelectorAll('.g-item')].length ? state.items : [];
  if (items.length === 0) return;
  toast(`Скачиваю ${items.length}…`);
  for (const item of items.slice(0, 10)) {
    await downloadItem(item);
    await new Promise((r) => setTimeout(r, 600));
  }
}

function copyLink() {
  const item = selected();
  if (!item) return;
  const share = new URL(location.href);
  share.searchParams.set('prompt', item.prompt);
  share.searchParams.set('style', item.style);
  share.searchParams.set('model', item.model);
  share.searchParams.set('size', item.size);
  share.searchParams.set('seed', String(item.seed));
  navigator.clipboard?.writeText(share.toString())
    .then(() => toast('Ссылка скопирована 🔗'))
    .catch(() => {
      prompt('Скопируйте ссылку:', share.toString());
    });
}

function reuseSelected() {
  const item = selected();
  if (item) reuseItem(item);
}

function reuseItem(item) {
  $('prompt').value = item.prompt;
  $('charCount').textContent = item.prompt.length;
  if (STYLES[item.style] !== undefined) $('style').value = item.style;
  if (MODEL_NAMES[item.model]) $('model').value = item.model;
  $('seed').value = String(item.seed);
  updateMeta();
  window.scrollTo({ top: 0, behavior: 'smooth' });
  $('prompt').focus();
  toast('Параметры подставлены — жмите «Сгенерировать»');
}

// =====================================================================
// Viewer
// =====================================================================

let viewerIndex = 0;

function openViewer(item) {
  if (!item) return;
  viewerIndex = Math.max(0, state.items.findIndex((i) => i.id === item.id));
  showViewerItem();
  $('viewer').hidden = false;
  document.body.style.overflow = 'hidden';
}

function showViewerItem() {
  const item = state.items[viewerIndex];
  if (!item) return;
  $('viewerImg').src = item.url;
  $('viewerImg').alt = item.prompt;
  $('viewerCaption').textContent = `${item.prompt} · ${STYLE_NAMES[item.style]} · ${item.size} · seed ${item.seed}`;
}

function stepViewer(dir) {
  if (state.items.length === 0) return;
  viewerIndex = (viewerIndex + dir + state.items.length) % state.items.length;
  showViewerItem();
}

function closeViewer() {
  $('viewer').hidden = true;
  document.body.style.overflow = '';
}

// =====================================================================
// Loader / status / toast
// =====================================================================

function startLoader() {
  $('previewLoader').hidden = false;
  state.startTime = Date.now();
  const tick = () => {
    const sec = Math.floor((Date.now() - state.startTime) / 1000);
    $('loaderText').textContent = `Рисую… ${sec} с`;
    // псевдо-прогресс: быстро до 85%, дальше медленно
    const p = Math.min(96, 8 + sec * 7 + Math.min(30, sec * 1.5));
    $('loadbarFill').style.width = p + '%';
  };
  tick();
  state.timer = setInterval(tick, 500);
}

function stopLoader() {
  clearInterval(state.timer);
  state.timer = null;
  $('loadbarFill').style.width = '100%';
  setTimeout(() => { $('previewLoader').hidden = true; }, 250);
}

function setStatus(text) {
  $('status').textContent = text;
}

let toastTimer = null;
function toast(text) {
  const t = $('toast');
  t.textContent = text;
  t.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { t.hidden = true; }, 2600);
}

function plural(n, one, few, many) {
  const m = n % 10, h = n % 100;
  if (m === 1 && h !== 11) return one;
  if (m >= 2 && m <= 4 && (h < 10 || h >= 20)) return few;
  return many;
}

init();
