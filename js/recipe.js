// Recipe — the contract between the AI director (server side) and the composer.
//
// A recipe is a fully specified musical brief. The AI fills it in, we validate
// it here (last line of defence before it reaches the composer), and the UI
// renders it. Keep in sync with `ai.py`.

export const STYLES = ['lofi', 'synthwave', 'ambient', 'techno', 'chiptune', 'classical'];
export const MOODS = ['dreamy', 'happy', 'sad', 'dark', 'epic'];
export const SCALES = ['major', 'minor', 'harmonic', 'dorian', 'phrygian', 'lydian', 'mixolydian'];
export const DURATIONS = [30, 60, 90, 120];
export const HARMONIC_RHYTHMS = [0.5, 1, 2];

export const KEY_NAMES_RU = ['До', 'До#', 'Ре', 'Ре#', 'Ми', 'Фа', 'Фа#', 'Соль', 'Соль#', 'Ля', 'Ля#', 'Си'];
export const STYLE_NAMES_RU = {
  lofi: 'Lo-fi', synthwave: 'Synthwave', ambient: 'Эмбиент',
  techno: 'Техно', chiptune: 'Chiptune', classical: 'Классика',
};
export const MOOD_NAMES_RU = {
  dreamy: 'Мечтательное', happy: 'Радостное', sad: 'Грустное',
  dark: 'Тёмное', epic: 'Эпичное',
};
export const SCALE_NAMES_RU = {
  major: 'мажор', minor: 'минор', harmonic: 'гарм. минор', dorian: 'дорийский',
  phrygian: 'фригийский', lydian: 'лидийский', mixolydian: 'миксолидийский',
};

const ROMAN = ['I', 'II', 'III', 'IV', 'V', 'VI', 'VII'];

const clamp = (v, lo, hi) => Math.max(lo, Math.min(hi, v));
const asInt = (v, fallback) => {
  const n = typeof v === 'number' ? v : parseFloat(v);
  return Number.isFinite(n) ? Math.round(n) : fallback;
};
const asFloat = (v, fallback) => {
  const n = typeof v === 'number' ? v : parseFloat(v);
  return Number.isFinite(n) ? n : fallback;
};
const nearest = (value, list) =>
  list.reduce((best, item) => (Math.abs(item - value) < Math.abs(best - value) ? item : best));
const clean = (v, limit) => (typeof v === 'string' ? v.replace(/\s+/g, ' ').trim().slice(0, limit) : '');
const oneOf = (v, list, fallback) => (list.includes(v) ? v : fallback);

/** Keep only sane degree arrays: 2..6 integers within 0..6. */
export function normaliseProgression(value) {
  if (!Array.isArray(value)) return null;
  const degrees = value.map((d) => (typeof d === 'number' ? d : parseInt(d, 10)));
  if (degrees.some((d) => !Number.isInteger(d) || d < 0 || d > 6)) return null;
  if (degrees.length < 2 || degrees.length > 6) return null;
  return degrees;
}

/** Clamp/validate whatever the model produced into a renderable recipe. */
export function normaliseRecipe(raw, current = null) {
  const src = raw && typeof raw === 'object' ? raw : {};
  const cur = (current && current.recipe) || current || {};

  const bpm = asInt(src.bpm ?? cur.bpm, 0);
  const key = ((asInt(src.key ?? cur.key, 0) % 12) + 12) % 12;
  const duration = nearest(asInt(src.duration ?? cur.duration, 60), DURATIONS);
  const hr = nearest(asFloat(src.harmonicRhythm ?? cur.harmonicRhythm, 1), HARMONIC_RHYTHMS);

  const progA = normaliseProgression(src.progressionA) || normaliseProgression(cur.progressionA) || [0, 5, 2, 6];
  let progB = normaliseProgression(src.progressionB) || normaliseProgression(cur.progressionB) || [0, 3, 4, 0];
  if (progA.join() === progB.join()) progB = progA.join() === [0, 3, 4, 0].join() ? [0, 6, 5, 6] : [0, 3, 4, 0];

  return {
    reply: clean(src.reply, 900) || 'Готово — собрал новый трек.',
    title: clean(src.title, 40) || clean(cur.title, 40) || 'Без названия',
    notes: clean(src.notes, 200),
    apply: src.apply === undefined ? true : Boolean(src.apply),
    seed: clean(src.seed, 24) || clean(cur.seed, 24) || 'track',
    style: oneOf(src.style, STYLES, oneOf(cur.style, STYLES, 'lofi')),
    mood: oneOf(src.mood, MOODS, oneOf(cur.mood, MOODS, 'dreamy')),
    scale: oneOf(src.scale, SCALES, oneOf(cur.scale, SCALES, 'minor')),
    key,
    bpm: bpm === 0 ? 0 : clamp(bpm, 60, 150),
    duration,
    harmonicRhythm: hr,
    progressionA: progA,
    progressionB: progB,
  };
}

export const roman = (degrees) => degrees.map((d) => ROMAN[d % 7]).join('–');

/** Human-readable rows for the recipe card. */
export function describeRecipe(r) {
  return [
    ['Стиль', STYLE_NAMES_RU[r.style] ?? r.style],
    ['Настроение', MOOD_NAMES_RU[r.mood] ?? r.mood],
    ['Тональность', `${KEY_NAMES_RU[r.key]} ${SCALE_NAMES_RU[r.scale] ?? r.scale}`],
    ['Темп', r.bpm ? `${r.bpm} BPM` : 'подберёт движок'],
    ['Длина', `~${r.duration} с`],
    ['Гармония', `${r.harmonicRhythm} акк./такт · ${roman(r.progressionA)} · ${roman(r.progressionB)}`],
  ];
}

/** The subset that actually changes the composition (text fields excluded). */
export function musicOverrides(r) {
  return {
    scale: r.scale,
    harmonicRhythm: r.harmonicRhythm,
    progressionA: r.progressionA.slice(),
    progressionB: r.progressionB.slice(),
  };
}

export const recipeToParams = (r) => ({
  style: r.style,
  mood: r.mood,
  key: r.key,
  scale: r.scale,
  bpm: r.bpm,
  duration: r.duration,
  hr: r.harmonicRhythm,
  progA: r.progressionA.join(','),
  progB: r.progressionB.join(','),
  title: r.title,
  seed: r.seed,
});

/** URL params that carry AI decisions and aren't already part of the plain link. */
export const AI_ONLY_PARAMS = ['scale', 'hr', 'progA', 'progB', 'title'];

export function recipeFromParams(params) {
  const parseProg = (s) => (s ? String(s).split(',').map((x) => parseInt(x, 10)) : null);
  return normaliseRecipe({
    apply: true,
    style: params.get('style'),
    mood: params.get('mood'),
    key: params.get('key'),
    scale: params.get('scale'),
    bpm: params.get('bpm'),
    duration: params.get('duration'),
    harmonicRhythm: params.get('hr'),
    progressionA: parseProg(params.get('progA')),
    progressionB: parseProg(params.get('progB')),
    title: params.get('title'),
    seed: params.get('seed'),
  });
}
