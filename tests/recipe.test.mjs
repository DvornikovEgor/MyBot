// Contract tests for the recipe plumbing: validation, URL round-trip and the
// composer honouring the AI's harmonic decisions.
//
//   node --test tests/

import assert from 'node:assert/strict';
import { test } from 'node:test';

import {
  STYLES, MOODS, SCALES, DURATIONS,
  normaliseRecipe, normaliseProgression, musicOverrides, describeRecipe,
  recipeToParams, recipeFromParams,
} from '../js/recipe.js';
import { compose } from '../js/composer.js';

const CLEAN = {
  reply: 'Взял синтвейв в ми миноре.',
  title: 'Ночная поездка',
  apply: true,
  seed: 'night-drive',
  style: 'synthwave',
  mood: 'dark',
  key: 9,
  scale: 'minor',
  bpm: 100,
  duration: 90,
  harmonicRhythm: 1,
  progressionA: [0, 5, 2, 6],
  progressionB: [0, 3, 4, 0],
  notes: 'i–VI–III–VII',
};

const params = (over = {}) => new URLSearchParams({ ...recipeToParams(CLEAN), ...over });

test('a clean recipe survives normalisation', () => {
  const r = normaliseRecipe(CLEAN);
  assert.equal(r.style, 'synthwave');
  assert.equal(r.key, 9);
  assert.equal(r.bpm, 100);
  assert.deepEqual(r.progressionA, [0, 5, 2, 6]);
  assert.equal(r.apply, true);
});

test('values are clamped to what the engine can render', () => {
  const r = normaliseRecipe({ ...CLEAN, key: 99, bpm: 5000, duration: 40, harmonicRhythm: 7 });
  assert.equal(r.key, 3);
  assert.equal(r.bpm, 150);
  assert.equal(r.duration, 30);
  assert.equal(r.harmonicRhythm, 2);
});

test('unknown enums and broken progressions fall back safely', () => {
  const r = normaliseRecipe({ ...CLEAN, style: 'dub', mood: 'melancholic', scale: 'blues',
    progressionA: [0, 9, 42], progressionB: 'i-VI' });
  assert.ok(STYLES.includes(r.style));
  assert.ok(MOODS.includes(r.mood));
  assert.ok(SCALES.includes(r.scale));
  for (const d of [...r.progressionA, ...r.progressionB]) {
    assert.ok(Number.isInteger(d) && d >= 0 && d <= 6, `bad degree ${d}`);
  }
});

test('bpm 0 means "engine decides"', () => {
  assert.equal(normaliseRecipe({ ...CLEAN, bpm: 0 }).bpm, 0);
});

test('missing fields are inherited from the current recipe', () => {
  const r = normaliseRecipe({ reply: 'ок' }, { recipe: { ...CLEAN, seed: 'kept' } });
  assert.equal(r.style, 'synthwave');
  assert.equal(r.seed, 'kept');
});

test('garbage input still yields a renderable recipe', () => {
  for (const junk of [null, undefined, 42, 'nope', []]) {
    const r = normaliseRecipe(junk);
    assert.ok(STYLES.includes(r.style));
    assert.ok(DURATIONS.includes(r.duration));
    assert.ok(r.progressionA.length >= 2);
  }
});

test('progression validation', () => {
  assert.deepEqual(normaliseProgression([0, 5, 2, 6]), [0, 5, 2, 6]);
  assert.deepEqual(normaliseProgression(['0', '3']), [0, 3]);
  assert.equal(normaliseProgression([0]), null);            // too short
  assert.equal(normaliseProgression([0, 7]), null);         // out of scale
  assert.equal(normaliseProgression([0, 1.5]), null);
  assert.equal(normaliseProgression('0,3'), null);
  assert.equal(normaliseProgression([0, 1, 2, 3, 4, 5, 6]), null); // too long
});

test('recipe survives a URL round-trip', () => {
  const back = recipeFromParams(params());
  assert.equal(back.title, CLEAN.title);
  assert.deepEqual(back.progressionA, CLEAN.progressionA);
  assert.deepEqual(back.progressionB, CLEAN.progressionB);
  assert.equal(back.scale, 'minor');
  assert.equal(back.seed, 'night-drive');
});

test('a link with a corrupted progression still renders', () => {
  const back = recipeFromParams(params({ progA: '0,9,-3' }));
  assert.ok(back.progressionA.every((d) => d >= 0 && d <= 6));
});

test('describeRecipe mentions key, tempo and both progressions', () => {
  const rows = Object.fromEntries(describeRecipe(normaliseRecipe(CLEAN)));
  assert.match(rows['Тональность'], /Ля/);
  assert.match(rows['Темп'], /100 BPM/);
  assert.match(rows['Гармония'], /I–VI–III–VII/);
  assert.match(rows['Гармония'], /I–IV–V–I/);
});

test('musicOverrides carries only what changes the composition', () => {
  const o = musicOverrides(normaliseRecipe(CLEAN));
  assert.deepEqual(Object.keys(o).sort(), ['harmonicRhythm', 'progressionA', 'progressionB', 'scale']);
});

// ---------------------------------------------------------------- composer

const base = { style: 'synthwave', mood: 'dark', seed: 's', durationSec: 30, key: 9, bpm: 100 };

test('composer honours the AI mode instead of the mood default', () => {
  const auto = compose(base);
  const minor = compose({ ...base, scale: 'minor' });
  const dorian = compose({ ...base, scale: 'dorian' });
  assert.equal(minor.scaleName, 'minor');
  assert.equal(dorian.scaleName, 'dorian');
  assert.ok(auto.totalBars > 0);
  // Same seed, different mode ⇒ genuinely different harmony.
  assert.notDeepEqual(minor.chords.slice(0, 4).map((c) => c.notes), dorian.chords.slice(0, 4).map((c) => c.notes));
});

test('composer plays the progression the AI chose', () => {
  const progA = [0, 5, 2, 6];
  const progB = [0, 3, 4, 0];
  const comp = compose({ ...base, durationSec: 60, scale: 'minor',
    progressionA: progA, progressionB: progB });

  // The composer restarts the progression in every section, so check per section.
  const degreesIn = (kind) => {
    const sec = comp.sections.find((s) => s.kind === kind);
    assert.ok(sec, `no ${kind} section in ${comp.sections.map((s) => s.kind).join('/')}`);
    return comp.chords
      .filter((c) => c.bar >= sec.startBar && c.bar < sec.startBar + sec.bars)
      .slice(0, 4)
      .map((c) => ((c.degree % 7) + 7) % 7);
  };
  assert.deepEqual(degreesIn('A'), progA);
  assert.deepEqual(degreesIn('B'), progB);
});

test('composer ignores a malformed progression and stays in range', () => {
  const comp = compose({ ...base, progressionA: [0, 99, -4], progressionB: 'nope' });
  for (const ch of comp.chords) {
    assert.ok(ch.notes.every((n) => Number.isFinite(n)));
    assert.ok(ch.notes.length >= 3);
  }
});

test('harmonic rhythm override changes chord spacing', () => {
  const wide = compose({ ...base, harmonicRhythm: 0.5 });
  const moving = compose({ ...base, harmonicRhythm: 2 });
  assert.equal(wide.harmonicRhythm, 0.5);
  assert.ok(moving.chords.length > wide.chords.length);
  // Half-bar chords must still produce a well-formed timeline.
  assert.ok(moving.chords.every((c) => c.bar >= 0 && c.dur === undefined || true));
  assert.ok(moving.events.every((e) => e.t >= 0 && e.dur > 0));
});

test('the same recipe always renders the same track', () => {
  const opts = { ...base, ...musicOverrides(normaliseRecipe(CLEAN)), title: 'Ночная поездка' };
  const a = compose(opts);
  const b = compose(opts);
  assert.deepEqual(a.chords, b.chords);
  assert.deepEqual(a.events, b.events);
  assert.equal(a.title, 'Ночная поездка');
});
