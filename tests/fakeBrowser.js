// Мини-подделка браузера для прогонов клиентского кода в Node.
// Реализует только браузерные API; логика игры остаётся настоящей.

const CTX_METHODS = new Set([
  'save', 'restore', 'translate', 'scale', 'rotate', 'transform', 'setTransform', 'resetTransform',
  'beginPath', 'closePath', 'moveTo', 'lineTo', 'arc', 'arcTo', 'ellipse', 'rect', 'roundRect',
  'quadraticCurveTo', 'bezierCurveTo', 'fill', 'stroke', 'clip', 'fillRect', 'strokeRect',
  'clearRect', 'fillText', 'strokeText', 'measureText', 'createLinearGradient', 'createRadialGradient',
  'createPattern', 'drawImage', 'setLineDash', 'getLineDash',
]);
const CTX_PROPS = new Set([
  'fillStyle', 'strokeStyle', 'lineWidth', 'lineCap', 'lineJoin', 'globalAlpha',
  'globalCompositeOperation', 'font', 'textAlign', 'textBaseline', 'shadowBlur', 'shadowColor',
  'filter', 'miterLimit', 'imageSmoothingEnabled', 'canvas', 'direction', 'lineDashOffset',
]);
const NUMERIC_ARG_METHODS = new Set([
  'translate', 'scale', 'rotate', 'moveTo', 'lineTo', 'arc', 'arcTo', 'ellipse', 'rect',
  'quadraticCurveTo', 'bezierCurveTo', 'fillRect', 'strokeRect', 'clearRect',
  'createLinearGradient', 'createRadialGradient',
]);

export class CtxError extends Error {}

export function makeContext(canvas) {
  const state = {};
  let calls = 0;
  const target = {
    canvas,
    get callCount() {
      return calls;
    },
  };
  return new Proxy(target, {
    get(obj, prop) {
      if (prop === 'canvas') return canvas;
      if (prop === 'callCount') return calls;
      if (CTX_PROPS.has(prop)) return state[prop];
      if (CTX_METHODS.has(prop)) {
        return (...args) => {
          calls += 1;
          if (NUMERIC_ARG_METHODS.has(prop)) {
            for (const a of args) {
              if (typeof a === 'number' && !Number.isFinite(a)) {
                throw new CtxError(`ctx.${prop} получил не-число: ${JSON.stringify(args)}`);
              }
            }
          }
          if (prop === 'fillText' || prop === 'strokeText') {
            if (typeof args[0] !== 'string') throw new CtxError(`ctx.${prop} ждёт строку, дано ${typeof args[0]}`);
            for (const a of args.slice(1)) {
              if (!Number.isFinite(a)) throw new CtxError(`ctx.${prop} координаты не числа: ${args}`);
            }
          }
          if (prop === 'measureText') return { width: String(args[0]).length * 7 };
          if (prop.startsWith('create')) {
            return { addColorStop: (o, c) => {
              if (!Number.isFinite(o)) throw new CtxError('addColorStop с не-числом');
              if (typeof c !== 'string') throw new CtxError('addColorStop ждёт строку цвета');
            } };
          }
          return undefined;
        };
      }
      throw new CtxError(`Неизвестное свойство 2D-контекста: ${String(prop)}`);
    },
    set(obj, prop, value) {
      if (!CTX_PROPS.has(prop)) throw new CtxError(`Запись в неизвестное свойство контекста: ${String(prop)}`);
      if ((prop === 'fillStyle' || prop === 'strokeStyle') && typeof value !== 'string' && typeof value !== 'object') {
        throw new CtxError(`ctx.${prop} = ${value}`);
      }
      if (prop === 'globalAlpha' && (!Number.isFinite(value) || value < 0 || value > 1)) {
        throw new CtxError(`globalAlpha вне диапазона: ${value}`);
      }
      state[prop] = value;
      return true;
    },
    has(obj, prop) {
      return CTX_METHODS.has(prop) || CTX_PROPS.has(prop);
    },
  });
}

export function makeElement(tag = 'div', id = '') {
  const el = {
    tagName: tag.toUpperCase(),
    id,
    children: [],
    listeners: {},
    dataset: {},
    style: {},
    value: '',
    textContent: '',
    disabled: false,
    checked: true,
    width: 0,
    height: 0,
    clientWidth: tag === 'canvas' ? 1280 : 0,
    clientHeight: tag === 'canvas' ? 720 : 0,
    offsetWidth: 100,
    _html: '',
    _classes: new Set(),
  };
  el.classList = {
    add: (...c) => c.forEach((x) => el._classes.add(x)),
    remove: (...c) => c.forEach((x) => el._classes.delete(x)),
    contains: (c) => el._classes.has(c),
    toggle: (c, force) => {
      const on = force === undefined ? !el._classes.has(c) : !!force;
      if (on) el._classes.add(c);
      else el._classes.delete(c);
      return on;
    },
  };
  Object.defineProperty(el, 'className', {
    get: () => [...el._classes].join(' '),
    set: (v) => {
      el._classes = new Set(String(v).split(/\s+/).filter(Boolean));
    },
  });
  Object.defineProperty(el, 'innerHTML', {
    get: () => el._html,
    set: (v) => {
      el._html = String(v);
      if (String(v) === '') el.children = [];
    },
  });
  el.appendChild = (child) => {
    child.parentElement = el;
    el.children.push(child);
    return child;
  };
  el.append = (...nodes) => nodes.forEach((n) => el.appendChild(n));
  el.remove = () => {};
  el.addEventListener = (ev, fn) => {
    (el.listeners[ev] ||= []).push(fn);
  };
  el.removeEventListener = (ev, fn) => {
    el.listeners[ev] = (el.listeners[ev] || []).filter((f) => f !== fn);
  };
  el.dispatch = (ev, evt = {}) => {
    for (const fn of el.listeners[ev] || []) fn({ preventDefault() {}, stopPropagation() {}, ...evt });
  };
  el.querySelectorAll = (sel) => el.children.filter((c) => matches(c, sel));
  el.querySelector = (sel) => el.children.find((c) => matches(c, sel)) || null;
  el.getContext = () => (el._ctx ||= makeContext(el));
  el.getBoundingClientRect = () => ({ left: 0, top: 0, width: 1280, height: 720 });
  el.focus = () => {};
  return el;
}

function matches(el, sel) {
  if (sel.startsWith('.')) return el._classes.has(sel.slice(1));
  const m = /^\[data-([\w-]+)="([^"]+)"\]$/.exec(sel);
  if (m) return el.dataset[m[1]] === m[2];
  if (/^[\w-]+$/.test(sel)) return el.tagName === sel.toUpperCase();
  return false;
}

/**
 * Собирает window/document/canvas/rAF по списку id из index.html.
 * Возвращает { window, document, elements, frames(), click(id) }.
 */
export function makeBrowser({ ids = [], width = 1280, height = 720 } = {}) {
  const elements = new Map();
  const rafQueue = [];
  const winListeners = {};

  for (const id of ids) {
    const tag = id.includes('frog') || id === 'game' ? 'canvas' : id.startsWith('opt-') ? (id === 'opt-name' ? 'input' : 'select') : 'div';
    const el = makeElement(tag, id);
    if (tag === 'canvas') {
      el.clientWidth = width;
      el.clientHeight = height;
    }
    elements.set(id, el);
  }
  // кнопки внутри sabotage-menu
  const sabMenu = elements.get('sabotage-menu');
  if (sabMenu) {
    for (const type of ['fog', 'comms']) {
      const b = makeElement('button');
      b.dataset.sab = type;
      sabMenu.appendChild(b);
    }
  }
  const nameInput = elements.get('opt-name');
  if (nameInput) nameInput.value = 'Тестер';
  for (const [id, val] of [['opt-players', '8'], ['opt-impostors', '1'], ['opt-tasks', '5']]) {
    if (elements.has(id)) elements.get(id).value = val;
  }

  const document = {
    getElementById: (id) => {
      if (!elements.has(id)) throw new Error(`В поддельном DOM нет элемента #${id}`);
      return elements.get(id);
    },
    createElement: (tag) => makeElement(tag),
    addEventListener: (ev, fn) => {
      (winListeners[ev] ||= []).push(fn);
    },
  };

  const win = {
    innerWidth: width,
    innerHeight: height,
    devicePixelRatio: 1,
    AudioContext: null,
    webkitAudioContext: null,
    addEventListener: (ev, fn) => {
      (winListeners[ev] ||= []).push(fn);
    },
    removeEventListener: () => {},
    requestAnimationFrame: (fn) => rafQueue.push(fn),
    cancelAnimationFrame: () => {},
    performance: { now: () => Date.now() },
    dispatch: (ev, evt = {}) => {
      for (const fn of winListeners[ev] || []) fn({ preventDefault() {}, stopPropagation() {}, ...evt });
    },
  };

  let clock = 0;
  return {
    window: win,
    document,
    elements,
    listeners: winListeners,
    get(id) {
      return elements.get(id);
    },
    /** Прогнать n кадров по dt секунд. */
    frames(n = 1, dt = 1 / 60) {
      for (let i = 0; i < n; i++) {
        const q = rafQueue.splice(0, rafQueue.length);
        if (!q.length) throw new Error('requestAnimationFrame больше не вызывается — игровой цикл встал');
        clock += dt * 1000;
        for (const fn of q) fn(clock);
      }
      return clock;
    },
    click(id, evt) {
      const el = typeof id === 'string' ? elements.get(id) : id;
      el.dispatch('click', evt);
    },
    key(code, type = 'keydown') {
      win.dispatch(type, { code, repeat: false });
    },
  };
}

export const INDEX_IDS = [
  'game', 'menu', 'menu-frog', 'opt-name', 'opt-players', 'opt-impostors', 'opt-tasks', 'btn-start',
  'reveal', 'reveal-card', 'reveal-frog', 'reveal-title', 'reveal-text',
  'hud', 'tasks-panel', 'tasks-title', 'task-bar', 'task-bar-fill', 'task-list', 'sabotage-banner', 'toast-wrap',
  'role-badge', 'action-bar', 'btn-use', 'btn-report', 'btn-kill', 'btn-vent', 'btn-sabotage',
  'btn-emergency', 'sabotage-menu', 'btn-pause',
  'meeting', 'meeting-title', 'meeting-sub', 'meeting-timer', 'meeting-timer-fill', 'vote-grid',
  'vote-status', 'btn-skip',
  'eject', 'eject-frog', 'eject-text',
  'pause', 'opt-sound', 'pause-info', 'btn-resume', 'btn-quit',
  'end', 'end-title', 'end-reason', 'end-impostors', 'end-stats', 'btn-again', 'btn-menu',
];
