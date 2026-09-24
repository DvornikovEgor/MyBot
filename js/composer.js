// Algorithmic composer: turns (style, mood, key, seed, length) into note events.
//
// Events: { track, t (beats), dur (beats), midi, vel, pan? }
// Tracks: 'lead' | 'pad' | 'comp' | 'bass' | 'arp' | 'drums'

import { Rng } from './rng.js';
import {
  SCALES, MOODS, STYLES, DRUM,
  degreeMidi, moveOnScale, buildChord, voiceLead, nearestChordTone,
} from './theory.js';

const BEATS_PER_BAR = 4;

export function compose(opts) {
  const seedStr = String(opts.seed ?? String(Math.floor(Math.random() * 1e9)));
  const rng = new Rng(seedStr + '|' + opts.style + '|' + opts.mood);
  const style = STYLES[opts.style] || STYLES.lofi;
  const mood = MOODS[opts.mood] || MOODS.dreamy;

  // --- tempo, key, length -------------------------------------------------
  let bpm = opts.bpm;
  if (!bpm) {
    bpm = Math.round(rng.float(style.bpmRange[0], style.bpmRange[1]) + mood.tempoBias);
    bpm = Math.max(55, Math.min(160, bpm));
  }
  const swing = style.swing[0] + rng.next() * (style.swing[1] - style.swing[0]);
  const scaleName = rng.pick(mood.scales);
  const scaleSteps = SCALES[scaleName].steps;
  const tonic = opts.key != null ? opts.key : rng.int(0, 11);
  const tonicMidi = 48 + tonic; // C3..B3 area as tonal center reference

  const targetSec = opts.durationSec || 60;
  let totalBars = Math.round((targetSec * bpm) / 60 / BEATS_PER_BAR);
  totalBars = Math.max(12, Math.min(64, totalBars));

  // --- structure: intro / A / B / A' / outro ------------------------------
  const introBars = totalBars >= 20 ? 4 : 2;
  const outroBars = totalBars >= 20 ? 4 : 2;
  const bodyBars = totalBars - introBars - outroBars;
  const sections = [{ name: 'Интро', startBar: 0, bars: introBars, kind: 'intro' }];
  {
    const chunk = bodyBars >= 24 ? 8 : bodyBars >= 12 ? 8 : Math.max(4, bodyBars);
    let bar = introBars;
    let idx = 0;
    const names = ['A', 'B', 'A′', 'B′', 'C'];
    while (bar < totalBars - outroBars) {
      const b = Math.min(chunk, totalBars - outroBars - bar);
      if (b < 3) {
        // fold tiny remainder into previous section
        sections[sections.length - 1].bars += b;
        bar += b;
        break;
      }
      const kind = idx % 2 === 0 ? 'A' : 'B';
      sections.push({ name: names[Math.min(idx, names.length - 1)], startBar: bar, bars: b, kind });
      bar += b;
      idx++;
    }
  }
  sections.push({ name: 'Аутро', startBar: totalBars - outroBars, bars: outroBars, kind: 'outro' });

  // --- harmony ------------------------------------------------------------
  const progA = style.progressions[rng.int(0, style.progressions.length - 1)];
  let progB = style.progressions[rng.int(0, style.progressions.length - 1)];
  if (progB === progA && style.progressions.length > 1) {
    progB = style.progressions[(style.progressions.indexOf(progA) + 1) % style.progressions.length];
  }

  const chords = []; // { bar, bars, degree, ...chord }
  {
    const hr = style.harmonicRhythm; // chords per bar (0.5 => one chord per 2 bars)
    const stepBars = 1 / hr;
    let prevVoicing = null;
    for (const sec of sections) {
      const prog = sec.kind === 'B' ? progB : progA;
      let k = 0;
      for (let b = 0; b < sec.bars; b += stepBars) {
        const deg = prog[k % prog.length];
        k++;
        const ch = buildChord(tonicMidi, scaleSteps, deg, style.seventh);
        const voicing = voiceLead(ch.notes, prevVoicing, 64);
        prevVoicing = voicing;
        chords.push({
          bar: sec.startBar + b,
          bars: Math.min(stepBars, sec.bars - b),
          degree: ch.degree,
          root: ch.root,
          quality: ch.quality,
          notes: ch.notes,
          voicing,
        });
      }
    }
  }

  const chordAtBar = (bar) => {
    let c = chords[0];
    for (const ch of chords) if (bar + 1e-6 >= ch.bar) c = ch;
    return c;
  };

  const events = [];
  const push = (track, t, dur, midi, vel, pan) => {
    if (dur <= 0) return;
    events.push({ track, t: Math.max(0, t), dur, midi, vel: Math.max(0.05, Math.min(1, vel)), ...(pan != null ? { pan } : {}) });
  };

  // Humanisation helpers (skip for drums — they stay quantised).
  const humT = () => rng.gauss() * 0.012;
  const humV = () => 1 + rng.gauss() * 0.05;
  const swingShift = (off16) => {
    // Delay 8th-note offbeats (2,6,10,14) and lighter 16th offbeats.
    if (off16 % 4 === 2) return swing * 0.25;
    if (off16 % 2 === 1) return swing * 0.08;
    return 0;
  };
  const tOf = (bar, off16) => bar * BEATS_PER_BAR + off16 / 4 + swingShift(off16);

  // --- melody (phrase-based with motif reuse) -----------------------------
  const [melMin, melMax] = style.melodyOctave;
  let motif = null;
  let lastMidi = Math.round((melMin + melMax) / 2);
  for (const sec of sections) {
    const singable = sec.kind === 'A' || sec.kind === 'B';
    const phraseBars = style.name === 'Эмбиент' ? 2 : 2;
    for (let p = 0; p * phraseBars < sec.bars; p++) {
      const startBar = sec.startBar + p * phraseBars;
      const barsInPhrase = Math.min(phraseBars, sec.bars - p * phraseBars);
      if (sec.kind === 'intro' && (p > 0 || rng.chance(0.5))) continue; // sparse intro
      if (sec.kind === 'outro' && p > 0) continue;
      const useMotif = singable && motif && p % 2 === 1;
      let rhythm, deltas;
      if (useMotif) {
        rhythm = motif.rhythm;
        deltas = motif.deltas.map((d) => (rng.chance(0.3) ? d + rng.int(-1, 1) : d));
      } else {
        rhythm = mutateRhythm(rng, rng.pick(style.melodyRhythms), singable ? 0.15 : 0.35);
        deltas = null;
      }
      if (!singable) {
        // thin out for intro/outro: keep only long notes
        rhythm = rhythm.filter(([, len]) => len >= 4).slice(0, 2);
        if (rhythm.length === 0) rhythm = [[0, 8]];
      }
      const contour = rng.weighted([[1, 3], [-1, 3], [0, 2]]);
      let degSteps = [];
      for (let i = 0; i < rhythm.length; i++) {
        const [off16, len16] = rhythm[i];
        const bar = startBar + Math.floor(off16 / 16);
        const off = off16 % 16;
        const ch = chordAtBar(bar);
        const strong = off % 8 === 0 || len16 >= 5;

        let midi;
        if (i === 0 && !useMotif) {
          // start near a chord tone in a comfortable register
          const target = ch.voicing[1 + rng.int(0, ch.voicing.length - 2)] ?? ch.voicing[0];
          midi = clampToRange(target + 12 * (rng.chance(0.5) ? 1 : 0), melMin, melMax);
        } else if (useMotif && deltas && deltas[i] != null) {
          midi = moveOnScale(lastMidi, deltas[i], tonicMidi, scaleSteps);
        } else {
          const step = rng.weighted([[-3, 1], [-2, 2], [-1, 5], [1, 5], [2, 2], [3, 1], [0, 1]]) + contour * (rng.chance(0.3) ? 1 : 0);
          midi = moveOnScale(lastMidi, step, tonicMidi, scaleSteps);
        }
        if (strong || rng.chance(0.35)) {
          const snapped = nearestChordTone(midi, ch.notes, 4);
          if (snapped != null) midi = snapped;
        }
        // keep in range and add gentle arc toward phrase end
        midi = clampToRange(midi, melMin, melMax);
        if (rng.chance(0.06)) midi += 12; // sparkle
        midi = clampToRange(midi, melMin, melMax);

        degSteps.push(midi - lastMidi);
        lastMidi = midi;
        const vel = (strong ? 0.78 : 0.6) * mood.energy * humV() * (sec.kind === 'B' ? 1.05 : 1);
        push('lead', tOf(bar, off) + humT(), (len16 / 4) * 0.95, midi, vel, rng.float(-0.2, 0.2));
      }
      if (!motif && singable && rhythm.length >= 2) {
        motif = { rhythm, deltas: degSteps.slice() };
      }
    }
  }

  // --- bass ---------------------------------------------------------------
  for (const sec of sections) {
    if (sec.kind === 'outro' && sec.bars <= 2) {
      // final low root
      const ch = chordAtBar(sec.startBar);
      push('bass', tOf(sec.startBar, 0), BEATS_PER_BAR * sec.bars, ch.root - 24, 0.55);
      continue;
    }
    for (let b = 0; b < sec.bars; b++) {
      const bar = sec.startBar + b;
      const ch = chordAtBar(bar);
      const pat = rng.pick(style.bassPattern);
      const last = sec.kind === 'outro' && b === sec.bars - 1;
      for (const [off16, len16, shift] of pat) {
        if (last && off16 > 4) continue;
        let midi = ch.root - 24 + shift;
        if (shift === 12) midi = ch.root - 12;
        if (shift === 7) midi = ch.root - 24 + 7;
        push('bass', tOf(bar, off16) + humT() * 0.5, (len16 / 4) * 0.9, midi, (0.7 * mood.energy) * humV());
      }
    }
  }

  // --- pad / comp ---------------------------------------------------------
  for (const ch of chords) {
    const sec = sections.find((s) => ch.bar >= s.startBar && ch.bar < s.startBar + s.bars) || sections[0];
    const t = tOf(ch.bar, 0);
    const dur = ch.bars * BEATS_PER_BAR;
    const light = sec.kind === 'intro' || sec.kind === 'outro';
    if (style.pad) {
      ch.voicing.forEach((midi, i) => {
        const vel = (light ? 0.3 : 0.42) * (mood.brightness) * humV();
        push('pad', t + i * 0.01, dur * 0.98, midi, vel, (i - (ch.voicing.length - 1) / 2) * 0.35);
      });
    }
    if (style.compRhythms.length) {
      const pat = style.compRhythms[rng.int(0, style.compRhythms.length - 1)];
      const bars = Math.max(1, Math.round(ch.bars));
      for (let b = 0; b < bars; b++) {
        if (light && b > 0) break;
        for (const [off16, len16] of pat) {
          if (light && rng.chance(0.5)) continue;
          ch.voicing.forEach((midi, i) => {
            push('comp', tOf(ch.bar + b, off16) + humT(), (len16 / 4) * 0.85, midi,
              (0.32 * mood.energy) * humV() * (off16 % 8 === 0 ? 1.1 : 0.9), (i - 1) * 0.2);
          });
        }
      }
    }
  }

  // --- arpeggio -----------------------------------------------------------
  if (style.arp) {
    const slow = style.arp === 'slowSixteenths';
    for (const sec of sections) {
      if (sec.kind === 'intro' && rng.chance(0.4)) { /* keep */ }
      if (sec.kind === 'outro') continue;
      const density = sec.kind === 'B' ? 1 : sec.kind === 'intro' ? 0.4 : 0.85;
      for (let b = 0; b < sec.bars; b++) {
        const bar = sec.startBar + b;
        const ch = chordAtBar(bar);
        const notes = ch.voicing;
        const upDown = rng.chance(0.6);
        const span = slow ? [0, 4, 8, 12] : [0, 2, 4, 6, 8, 10, 12, 14, 1, 3, 5, 7, 9, 11, 13, 15];
        const order = slow ? span : (upDown ? span : span.slice().reverse());
        let i = 0;
        for (const off16 of order) {
          if (slow && !rng.chance(density)) { i++; continue; }
          if (!slow && rng.chance(1 - density)) { i++; continue; }
          const base = notes[i % notes.length];
          let midi = base + (Math.floor(i / notes.length) % 2 === 1 ? 12 : 0);
          if (!slow) midi += sec.kind === 'B' ? 12 : 0;
          midi = clampToRange(midi, 55, 88);
          push('arp', tOf(bar, off16), slow ? 0.5 : 0.2, midi,
            (slow ? 0.25 : 0.3) * mood.energy * humV(), rng.float(-0.5, 0.5));
          i++;
        }
      }
    }
  }

  // --- drums --------------------------------------------------------------
  if (style.drums) {
    for (const sec of sections) {
      const full = sec.kind === 'A' || sec.kind === 'B';
      for (let b = 0; b < sec.bars; b++) {
        const bar = sec.startBar + b;
        const lastBar = b === sec.bars - 1;
        const fill = full && lastBar && sec.bars >= 4 && rng.chance(0.7);

        if (sec.kind !== 'intro' || b >= 1) {
          for (const off16 of rng.pick(style.drums.kick)) {
            push('drums', tOf(bar, off16), 0.25, DRUM.KICK, 0.95 * humV() * 0.98);
          }
        }
        if (full || (sec.kind === 'outro' && b === 0)) {
          for (const off16 of sec.kind === 'outro' ? [0] : rng.pick(style.drums.snare)) {
            push('drums', tOf(bar, off16), 0.25, DRUM.SNARE, 0.75 * mood.energy * humV());
          }
        }
        // hats
        const hats = [];
        if (style.drums.hats === 'eighthsSwing' || style.drums.hats === 'eighths') {
          for (let o = 0; o < 16; o += 2) hats.push([o, o === 14 && rng.chance(0.3) ? DRUM.OPENHAT : DRUM.HAT]);
        } else if (style.drums.hats === 'offbeats') {
          for (let o = 2; o < 16; o += 4) hats.push([o, DRUM.HAT]);
        } else if (style.drums.hats === 'offbeats16') {
          for (let o = 2; o < 16; o += 2) hats.push([o, o % 8 === 6 && rng.chance(0.25) ? DRUM.OPENHAT : DRUM.HAT]);
        }
        const hatDensity = sec.kind === 'intro' ? 0.5 : sec.kind === 'outro' ? (b < sec.bars - 1 ? 0.6 : 0.2) : 0.92;
        for (const [off16, note] of hats) {
          if (rng.chance(1 - hatDensity)) continue;
          push('drums', tOf(bar, off16), 0.1, note, (off16 % 4 === 2 ? 0.4 : 0.55) * humV());
        }
        // ghost snares (lo-fi flavour)
        if (full && style.name === 'Lo-fi' && rng.chance(0.35)) {
          push('drums', tOf(bar, rng.pick([7, 15])), 0.1, DRUM.RIM, 0.25);
        }
        // fill: toms / snare roll in the last beats
        if (fill) {
          const start = rng.chance(0.5) ? 8 : 12;
          for (let o = start; o < 16; o++) {
            if (rng.chance(0.75)) {
              const note = o % 2 === 0 ? DRUM.TOM : DRUM.TOM2;
              push('drums', tOf(bar, o), 0.12, note, 0.4 + (o - start) * 0.05);
            }
          }
          push('drums', tOf(bar, 15), 0.1, DRUM.SNARE, 0.5);
        }
      }
    }
  }

  events.sort((a, b) => a.t - b.t);

  return {
    seed: seedStr,
    style: opts.style,
    styleName: style.name,
    mood: opts.mood,
    moodName: mood.name,
    bpm,
    swing,
    tonic,
    scaleName,
    keyName: `${['До', 'До#', 'Ре', 'Ре#', 'Ми', 'Фа', 'Фа#', 'Соль', 'Соль#', 'Ля', 'Ля#', 'Си'][tonic]} ${SCALES[scaleName].name}`,
    totalBars,
    beatsPerBar: BEATS_PER_BAR,
    sections,
    chords,
    events,
    durationSec: totalBars * BEATS_PER_BAR * (60 / bpm),
  };
}

function clampToRange(midi, lo, hi) {
  while (midi < lo) midi += 12;
  while (midi > hi) midi -= 12;
  return midi;
}

function mutateRhythm(rng, rhythm, amount) {
  return rhythm.map(([off, len]) => {
    if (rng.chance(amount)) {
      const nOff = Math.max(0, Math.min(15, off + rng.pick([-2, -1, 1, 2])));
      return [nOff, len];
    }
    return [off, len];
  }).sort((a, b) => a[0] - b[0]);
}
