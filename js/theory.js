// Music theory helpers: scales, chords, voice leading, style / mood presets.

export const NOTE_NAMES = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B'];
export const NOTE_NAMES_RU = ['До', 'До#', 'Ре', 'Ре#', 'Ми', 'Фа', 'Фа#', 'Соль', 'Соль#', 'Ля', 'Ля#', 'Си'];

export const SCALES = {
  major:      { name: 'мажор',            steps: [0, 2, 4, 5, 7, 9, 11] },
  minor:      { name: 'минор',            steps: [0, 2, 3, 5, 7, 8, 10] },
  harmonic:   { name: 'гарм. минор',      steps: [0, 2, 3, 5, 7, 8, 11] },
  dorian:     { name: 'дорийский',        steps: [0, 2, 3, 5, 7, 9, 10] },
  phrygian:   { name: 'фригийский',       steps: [0, 1, 3, 5, 7, 8, 10] },
  lydian:     { name: 'лидийский',        steps: [0, 2, 4, 6, 7, 9, 11] },
  mixolydian: { name: 'миксолидийский',   steps: [0, 2, 4, 5, 7, 9, 10] },
};

/** Moods steer scale choice, tempo and energy. */
export const MOODS = {
  happy:   { name: 'Радостное',   scales: ['major', 'lydian', 'mixolydian'], tempoBias: +10, energy: 1.0, brightness: 1.1 },
  sad:     { name: 'Грустное',    scales: ['minor', 'dorian'],                tempoBias: -14, energy: 0.7, brightness: 0.85 },
  dreamy:  { name: 'Мечтательное', scales: ['lydian', 'major', 'dorian'],    tempoBias: -8,  energy: 0.6, brightness: 1.0 },
  dark:    { name: 'Тёмное',      scales: ['phrygian', 'minor', 'harmonic'],  tempoBias: -4,  energy: 0.9, brightness: 0.7 },
  epic:    { name: 'Эпичное',     scales: ['minor', 'harmonic', 'dorian'],    tempoBias: +6,  energy: 1.15, brightness: 1.05 },
};

/**
 * Style presets: tempo range, groove, harmony, rhythm templates and
 * per-track instrument characters consumed by the synth engine.
 * Rhythm templates use 16th-note steps inside a 4/4 bar (0..15).
 */
export const STYLES = {
  lofi: {
    name: 'Lo-fi',
    bpmRange: [70, 88],
    swing: [0.08, 0.16],
    seventh: true,
    harmonicRhythm: 1,             // chords per bar
    melodyOctave: [52, 74],
    progressions: [
      [0, 5, 1, 4],                // I vi ii V
      [1, 4, 0, 0],                // ii V I I
      [5, 3, 0, 4],                // vi IV I V
      [0, 3, 5, 4],                // I IV vi V
    ],
    melodyRhythms: [
      [[0, 4], [4, 2], [6, 2], [8, 4], [12, 4]],
      [[0, 3], [3, 3], [6, 2], [8, 4], [12, 2], [14, 2]],
      [[0, 2], [2, 2], [4, 4], [8, 2], [10, 2], [12, 4]],
      [[0, 4], [4, 4], [8, 3], [11, 3], [14, 2]],
    ],
    bassPattern: [                 // [off16, len16, degreeShift]
      [[0, 6, 0], [6, 2, 7], [8, 4, 0], [14, 2, 12]],
      [[0, 4, 0], [6, 2, 12], [8, 6, 0]],
      [[0, 3, 0], [3, 3, 7], [6, 2, 0], [10, 4, 12], [14, 2, 0]],
    ],
    compRhythms: [
      [[0, 3], [6, 2], [10, 4]],
      [[2, 2], [6, 2], [12, 4]],
      [[0, 4], [8, 2], [11, 3]],
      [[4, 4], [10, 3], [14, 2]],
    ],
    drums: {
      kick:  [[0, 10], [0, 6, 10], [0, 3, 10], [0, 6, 8, 10]],
      snare: [[4, 12], [4, 12, 15], [4, 12]],
      hats:  'eighthsSwing',
    },
    arp: null,
    pad: 'soft',
    reverb: { size: 1.6, mix: 0.16 },
    delay: { beats: 0.75, fb: 0.22, mix: 0.10 },
    duck: 0,
    vinyl: true,
  },

  synthwave: {
    name: 'Synthwave',
    bpmRange: [95, 118],
    swing: [0, 0],
    seventh: false,
    harmonicRhythm: 1,
    melodyOctave: [55, 81],
    progressions: [
      [0, 5, 2, 6],                // i VI III VII
      [0, 6, 5, 6],                // i VII VI VII
      [0, 3, 5, 6],                // i iv VI VII
      [0, 5, 3, 4],                // i VI iv V
    ],
    melodyRhythms: [
      [[0, 4], [4, 4], [8, 2], [10, 2], [12, 4]],
      [[0, 2], [2, 2], [4, 4], [8, 6], [14, 2]],
      [[0, 6], [6, 2], [8, 4], [12, 4]],
      [[0, 3], [3, 5], [8, 4], [12, 2], [14, 2]],
    ],
    bassPattern: [
      [[0, 2, 0], [2, 2, 0], [4, 2, 0], [6, 2, 0], [8, 2, 0], [10, 2, 0], [12, 2, 0], [14, 2, 0]],
      [[0, 2, 0], [2, 2, 12], [4, 2, 0], [6, 2, 12], [8, 2, 0], [10, 2, 12], [12, 2, 0], [14, 2, 7]],
      [[0, 4, 0], [4, 2, 0], [6, 2, 12], [8, 4, 0], [12, 2, 0], [14, 2, 7]],
    ],
    compRhythms: [],
    drums: {
      kick:  [[0, 4, 8, 12]],
      snare: [[4, 12]],
      hats:  'offbeats',
    },
    arp: 'sixteenths',
    pad: 'wide',
    reverb: { size: 2.4, mix: 0.24 },
    delay: { beats: 0.375, fb: 0.32, mix: 0.2 },
    duck: 0.55,
    vinyl: false,
  },

  ambient: {
    name: 'Эмбиент',
    bpmRange: [60, 76],
    swing: [0, 0],
    seventh: true,
    harmonicRhythm: 0.5,           // one chord per two bars
    melodyOctave: [55, 76],
    progressions: [
      [0, 5, 2, 6],
      [0, 2, 5, 3],
      [0, 3, 5, 4],
    ],
    melodyRhythms: [
      [[0, 8], [8, 8]],
      [[0, 6], [8, 4], [14, 2]],
      [[0, 4], [6, 4], [12, 4]],
      [[0, 12], [12, 4]],
    ],
    bassPattern: [
      [[0, 16, 0]],
      [[0, 8, 0], [8, 8, 7]],
    ],
    compRhythms: [],
    drums: null,
    arp: 'slowSixteenths',
    pad: 'airy',
    reverb: { size: 3.4, mix: 0.36 },
    delay: { beats: 1.5, fb: 0.4, mix: 0.22 },
    duck: 0,
    vinyl: false,
  },

  techno: {
    name: 'Техно',
    bpmRange: [120, 136],
    swing: [0, 0],
    seventh: false,
    harmonicRhythm: 1,
    melodyOctave: [55, 79],
    progressions: [
      [0, 0, 6, 6],
      [0, 5, 6, 6],
      [0, 0, 0, 0],
      [0, 3, 6, 0],
    ],
    melodyRhythms: [
      [[0, 2], [2, 2], [4, 2], [8, 2], [10, 2], [14, 2]],
      [[0, 4], [6, 2], [8, 4], [14, 2]],
      [[2, 2], [6, 2], [10, 2], [12, 4]],
      [[0, 2], [4, 2], [6, 2], [10, 2], [12, 2], [14, 2]],
    ],
    bassPattern: [
      [[2, 2, 0], [6, 2, 0], [10, 2, 0], [14, 2, 0]],
      [[2, 2, 0], [6, 2, 12], [10, 2, 0], [14, 2, 7]],
      [[0, 2, 0], [3, 1, 0], [6, 2, 0], [10, 2, 0], [14, 2, 0]],
    ],
    compRhythms: [
      [[2, 2], [6, 2], [10, 2], [14, 2]],
      [[4, 4], [12, 4]],
    ],
    drums: {
      kick:  [[0, 4, 8, 12]],
      snare: [[4, 12]],
      hats:  'offbeats16',
    },
    arp: null,
    pad: 'stabs',
    reverb: { size: 1.4, mix: 0.12 },
    delay: { beats: 0.25, fb: 0.26, mix: 0.12 },
    duck: 0.6,
    vinyl: false,
  },

  chiptune: {
    name: 'Chiptune',
    bpmRange: [118, 148],
    swing: [0, 0],
    seventh: false,
    harmonicRhythm: 1,
    melodyOctave: [60, 84],
    progressions: [
      [0, 4, 5, 3],                // I V vi IV
      [0, 3, 4, 0],                // I IV V I
      [5, 3, 0, 4],                // vi IV I V
    ],
    melodyRhythms: [
      [[0, 2], [2, 2], [4, 2], [6, 2], [8, 2], [10, 2], [12, 4]],
      [[0, 1], [1, 1], [2, 2], [4, 2], [6, 2], [8, 4], [12, 4]],
      [[0, 2], [2, 2], [4, 4], [8, 2], [10, 2], [12, 2], [14, 2]],
      [[0, 3], [3, 1], [4, 2], [8, 3], [11, 1], [12, 4]],
    ],
    bassPattern: [
      [[0, 2, 0], [2, 2, 12], [4, 2, 0], [6, 2, 12], [8, 2, 0], [10, 2, 12], [12, 2, 0], [14, 2, 12]],
      [[0, 2, 0], [4, 2, 0], [8, 2, 7], [12, 2, 0]],
    ],
    compRhythms: [],
    drums: {
      kick:  [[0, 8], [0, 8, 12], [0, 4, 8, 12]],
      snare: [[4, 12]],
      hats:  'eighths',
    },
    arp: 'sixteenths',
    pad: null,
    reverb: { size: 0.8, mix: 0.06 },
    delay: { beats: 0.25, fb: 0.18, mix: 0.08 },
    duck: 0,
    vinyl: false,
  },

  classical: {
    name: 'Классика',
    bpmRange: [72, 104],
    swing: [0, 0],
    seventh: true,
    harmonicRhythm: 1,
    melodyOctave: [55, 81],
    progressions: [
      [0, 5, 3, 4],                // I vi IV V
      [0, 3, 1, 4],                // I IV ii V
      [0, 2, 3, 4],                // I iii IV V
      [5, 3, 0, 4],                // vi IV I V
    ],
    melodyRhythms: [
      [[0, 4], [4, 4], [8, 2], [10, 2], [12, 4]],
      [[0, 2], [2, 2], [4, 4], [8, 4], [12, 4]],
      [[0, 6], [6, 2], [8, 8]],
      [[0, 3], [3, 3], [6, 2], [8, 4], [12, 4]],
    ],
    bassPattern: [
      [[0, 8, 0], [8, 8, 0]],
      [[0, 4, 0], [4, 4, 7], [8, 4, 0], [12, 4, 7]],
    ],
    compRhythms: [                  // broken-chord accompaniment
      [[0, 2], [2, 2], [4, 2], [6, 2], [8, 2], [10, 2], [12, 2], [14, 2]],
    ],
    drums: null,
    arp: null,
    pad: 'strings',
    reverb: { size: 2.6, mix: 0.26 },
    delay: { beats: 0, fb: 0, mix: 0 },
    duck: 0,
    vinyl: false,
  },
};

export function midiToFreq(midi) {
  return 440 * Math.pow(2, (midi - 69) / 12);
}

export function noteName(midi) {
  const n = NOTE_NAMES[((midi % 12) + 12) % 12];
  const oct = Math.floor(midi / 12) - 1;
  return `${n}${oct}`;
}

/** MIDI pitch of scale degree `deg` (may exceed the scale length: wraps octaves). */
export function degreeMidi(tonicMidi, scaleSteps, deg) {
  const len = scaleSteps.length;
  const oct = Math.floor(deg / len);
  const idx = ((deg % len) + len) % len;
  return tonicMidi + oct * 12 + scaleSteps[idx];
}

/** Move `steps` scale steps up (positive) or down (negative) from midi. */
export function moveOnScale(midi, steps, tonicMidi, scaleSteps) {
  // Find current degree index closest to midi, then shift.
  let best = 0;
  let bestDist = 1e9;
  for (let d = -scaleSteps.length; d <= scaleSteps.length * 2; d++) {
    const m = degreeMidi(tonicMidi, scaleSteps, d);
    const dist = Math.abs(m - midi);
    if (dist < bestDist) {
      bestDist = dist;
      best = d;
    }
  }
  return degreeMidi(tonicMidi, scaleSteps, best + steps);
}

/**
 * Build a diatonic chord on scale degree `deg` (0 = tonic triad).
 * Returns { notes: [midi...] with root nearest to rootMidi, root, quality }.
 */
export function buildChord(tonicMidi, scaleSteps, deg, seventh, rootMidi) {
  const stack = seventh ? [0, 2, 4, 6] : [0, 2, 4];
  let root = degreeMidi(tonicMidi, scaleSteps, deg);
  if (rootMidi !== undefined) {
    while (root - rootMidi > 6) root -= 12;
    while (rootMidi - root > 6) root += 12;
  }
  const rootDeg = degreeMidi(0, scaleSteps, deg);
  const chordNotes = stack.map((s) => root + (degreeMidi(0, scaleSteps, deg + s) - rootDeg));
  const quality = chordQuality(chordNotes, seventh);
  return { notes: chordNotes, root, quality, degree: deg };
}

function chordQuality(notes, seventh) {
  const rel = notes.map((n) => n - notes[0]);
  const third = rel[1], fifth = rel[2], sev = rel[3];
  let q;
  if (third === 4 && fifth === 7) q = sev === undefined ? 'maj' : sev === 11 ? 'maj7' : '7';
  else if (third === 3 && fifth === 7) q = sev === undefined ? 'min' : sev === 10 ? 'min7' : '7';
  else if (third === 3 && fifth === 6) q = sev === undefined ? 'dim' : 'dim7';
  else if (third === 4 && fifth === 8) q = 'aug';
  else q = 'maj';
  return q;
}

const ROMAN = ['I', 'II', 'III', 'IV', 'V', 'VI', 'VII'];

export function romanLabel(chord) {
  const base = ROMAN[((chord.degree % 7) + 7) % 7];
  switch (chord.quality) {
    case 'min': return base.toLowerCase();
    case 'min7': return base.toLowerCase() + '7';
    case 'dim': return base.toLowerCase() + '°';
    case 'dim7': return base.toLowerCase() + '°7';
    case 'aug': return base + '+';
    case 'maj7': return base + 'maj7';
    case '7': return base + '7';
    default: return base;
  }
}

/**
 * Pick an inversion of `chordNotes` whose pitches sit closest to `prevNotes`
 * (smooth voice leading). Root is forced to `bassMidi` octave area separately.
 */
export function voiceLead(chordNotes, prevNotes, center = 64) {
  const candidates = [];
  for (let inv = 0; inv < chordNotes.length; inv++) {
    const voicing = chordNotes.map((_, i) => {
      const n = chordNotes[(i + inv) % chordNotes.length];
      let m = n;
      while (m < center - 7) m += 12;
      while (m > center + 9) m -= 12;
      return m;
    });
    voicing.sort((a, b) => a - b);
    candidates.push(voicing);
  }
  if (!prevNotes || prevNotes.length === 0) return candidates[0];
  let best = candidates[0];
  let bestCost = Infinity;
  for (const c of candidates) {
    let cost = 0;
    for (const p of prevNotes) {
      let d = Infinity;
      for (const q of c) d = Math.min(d, Math.abs(p - q));
      cost += d;
    }
    if (cost < bestCost) {
      bestCost = cost;
      best = c;
    }
  }
  return best;
}

export function nearestChordTone(midi, chordNotes, maxDist = 4) {
  let best = null;
  let bestDist = Infinity;
  for (const n of chordNotes) {
    for (let oct = -2; oct <= 2; oct++) {
      const m = n + oct * 12;
      const d = Math.abs(m - midi);
      if (d < bestDist) {
        bestDist = d;
        best = m;
      }
    }
  }
  return bestDist <= maxDist ? best : null;
}

/** General-MIDI-ish drum note numbers used as event "pitches". */
export const DRUM = { KICK: 36, SNARE: 38, HAT: 42, OPENHAT: 46, CLAP: 39, RIM: 37, TOM: 45, TOM2: 47 };
