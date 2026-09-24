// UI, player, piano roll and spectrum visualiser.

import { compose } from './composer.js';
import { renderComposition } from './engine.js';
import { audioBufferToWav } from './wav.js';
import { NOTE_NAMES, DRUM } from './theory.js';

const $ = (id) => document.getElementById(id);

const state = {
  comp: null,
  buffer: null,
  audioCtx: null,
  analyser: null,
  masterGain: null,
  src: null,
  playing: false,
  loop: true,
  startedAt: 0,   // ctx time corresponding to offset 0
  offset: 0,      // seconds already played before current start
  rollCanvas: document.createElement('canvas'),
  generating: false,
};

const TRACK_COLORS = {
  lead: '#a78bfa',
  pad: '#38bdf8',
  comp: '#34d399',
  bass: '#fbbf24',
  arp: '#f472b6',
};

const KEY_NAMES = ['До', 'До#', 'Ре', 'Ре#', 'Ми', 'Фа', 'Фа#', 'Соль', 'Соль#', 'Ля', 'Ля#', 'Си'];

// =====================================================================
// Init
// =====================================================================

function init() {
  // URL params
  const params = new URLSearchParams(location.search);
  if (params.get('style')) $('style').value = params.get('style');
  if (params.get('mood')) $('mood').value = params.get('mood');
  if (params.get('duration')) $('duration').value = params.get('duration');
  if (params.get('key')) $('key').value = params.get('key');
  if (params.get('seed')) $('seed').value = params.get('seed');
  else $('seed').value = String(Math.floor(Math.random() * 999999));
  $('bpmAuto').checked = !params.get('bpm');
  if (params.get('bpm')) $('bpm').value = params.get('bpm');
  syncBpmUi();

  $('generate').addEventListener('click', generate);
  $('randomSeed').addEventListener('click', () => {
    $('seed').value = String(Math.floor(Math.random() * 999999));
    generate();
  });
  $('playBtn').addEventListener('click', togglePlay);
  $('stopBtn').addEventListener('click', () => stopPlayback(true));
  $('loopBtn').addEventListener('click', () => {
    state.loop = !state.loop;
    if (state.src) state.src.loop = state.loop;
    $('loopBtn').classList.toggle('active', state.loop);
  });
  $('download').addEventListener('click', downloadWav);
  $('volume').addEventListener('input', (e) => {
    if (state.masterGain) state.masterGain.gain.value = Number(e.target.value);
  });
  $('bpmAuto').addEventListener('change', syncBpmUi);
  $('bpm').addEventListener('input', () => {
    $('bpmVal').textContent = $('bpm').value;
  });
  $('seed').addEventListener('keydown', (e) => {
    if (e.key === 'Enter') generate();
  });
  $('progress').addEventListener('pointerdown', (e) => {
    if (!state.buffer) return;
    const rect = $('progress').getBoundingClientRect();
    const frac = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width));
    seekTo(frac * state.buffer.duration);
  });
  window.addEventListener('keydown', (e) => {
    if (e.target.tagName === 'INPUT' || e.target.tagName === 'SELECT') return;
    if (e.code === 'Space') {
      e.preventDefault();
      togglePlay();
    }
    if (e.key === 'g' || e.key === 'G' || e.key === 'п' || e.key === 'П') generate();
  });
  window.addEventListener('resize', () => {
    if (state.comp) drawRoll(state.comp);
    fitCanvas($('vis'));
    fitCanvas($('roll'));
    if (state.comp) blitRoll();
  });

  $('loopBtn').classList.add('active');
  fitCanvas($('vis'));
  fitCanvas($('roll'));
  generate();
}

function syncBpmUi() {
  const auto = $('bpmAuto').checked;
  $('bpm').disabled = auto;
  $('bpmVal').textContent = auto ? 'авто' : $('bpm').value;
}

// =====================================================================
// Generation
// =====================================================================

async function generate() {
  if (state.generating) return;
  state.generating = true;
  stopPlayback(true);
  state.buffer = null;
  setButtons(false);
  $('status').textContent = 'Сочиняю мелодию…';
  $('generate').classList.add('busy');

  const seed = $('seed').value.trim() || String(Math.floor(Math.random() * 999999));
  const style = $('style').value;
  const mood = $('mood').value;
  const durationSec = Number($('duration').value);
  const key = $('key').value === 'rand' ? null : Number($('key').value);
  const bpm = $('bpmAuto').checked ? null : Number($('bpm').value);

  // Yield a frame so the status text paints.
  await new Promise((r) => requestAnimationFrame(() => setTimeout(r, 0)));

  try {
    const comp = compose({ style, mood, seed, durationSec, key, bpm });
    state.comp = comp;
    drawRoll(comp);
    blitRoll();
    updateMeta(comp);

    $('status').textContent = 'Синтезирую звук…';
    await new Promise((r) => requestAnimationFrame(() => setTimeout(r, 0)));
    state.buffer = await renderComposition(comp);
    setButtons(true);
    $('status').textContent =
      `Готово · ${comp.totalBars} тактов · ${comp.bpm} BPM · ${comp.keyName} · сид ${comp.seed}`;
    updateUrl({ seed, style, mood, duration: durationSec, key: $('key').value, bpm: $('bpmAuto').checked ? null : comp.bpm });
  } catch (err) {
    console.error(err);
    $('status').textContent = 'Ошибка: ' + err.message;
  } finally {
    state.generating = false;
    $('generate').classList.remove('busy');
  }
}

function updateMeta(comp) {
  const names = comp.chords.map(chordDisplayName);
  const uniq = [];
  for (const n of names) if (uniq[uniq.length - 1] !== n) uniq.push(n);
  $('chords').textContent = uniq.join('  ·  ');
  $('structure').textContent = comp.sections.map((s) => `${s.name} (${s.bars})`).join(' → ');
  $('meta').textContent =
    `${comp.styleName} · ${comp.moodName} · ${comp.bpm} BPM · ${comp.keyName} · сид ${comp.seed}`;
}

function chordDisplayName(ch) {
  const root = NOTE_NAMES[((ch.root % 12) + 12) % 12];
  const suf = { maj: '', min: 'm', min7: 'm7', maj7: 'maj7', '7': '7', dim: 'dim', dim7: 'dim7', aug: 'aug' }[ch.quality] ?? '';
  return root + suf;
}

function updateUrl(p) {
  const q = new URLSearchParams();
  if (p.seed) q.set('seed', p.seed);
  if (p.style) q.set('style', p.style);
  if (p.mood) q.set('mood', p.mood);
  if (p.duration) q.set('duration', p.duration);
  if (p.key && p.key !== 'rand') q.set('key', p.key);
  if (p.bpm) q.set('bpm', p.bpm);
  history.replaceState(null, '', '?' + q.toString());
}

function setButtons(ready) {
  $('playBtn').disabled = !ready;
  $('stopBtn').disabled = !ready;
  $('download').disabled = !ready;
}

// =====================================================================
// Playback
// =====================================================================

function ensureCtx() {
  if (state.audioCtx) return;
  state.audioCtx = new (window.AudioContext || window.webkitAudioContext)();
  state.analyser = state.audioCtx.createAnalyser();
  state.analyser.fftSize = 2048;
  state.analyser.smoothingTimeConstant = 0.82;
  state.masterGain = state.audioCtx.createGain();
  state.masterGain.gain.value = Number($('volume').value);
  state.analyser.connect(state.masterGain).connect(state.audioCtx.destination);
}

function togglePlay() {
  if (!state.buffer) return;
  if (state.playing) {
    state.offset = position();
    stopSource();
    state.playing = false;
    updatePlayBtn();
  } else {
    play();
  }
}

function play() {
  if (!state.buffer) return;
  ensureCtx();
  state.audioCtx.resume();
  if (state.offset >= state.buffer.duration - 0.05) state.offset = 0;
  startSource(state.offset);
  state.playing = true;
  updatePlayBtn();
  requestAnimationFrame(tick);
}

function startSource(offsetSec) {
  stopSource();
  const src = state.audioCtx.createBufferSource();
  src.buffer = state.buffer;
  src.loop = state.loop;
  src.connect(state.analyser);
  src.onended = () => {
    if (state.src === src && state.playing && !state.loop) {
      state.playing = false;
      state.offset = 0;
      updatePlayBtn();
    }
  };
  src.start(0, offsetSec % state.buffer.duration);
  state.src = src;
  state.startedAt = state.audioCtx.currentTime - offsetSec;
}

function stopSource() {
  if (state.src) {
    try { state.src.onended = null; state.src.stop(); } catch { /* already stopped */ }
    state.src.disconnect();
    state.src = null;
  }
}

function stopPlayback(reset) {
  stopSource();
  state.playing = false;
  if (reset) state.offset = 0;
  updatePlayBtn();
  updateProgressUI(0, 0);
  drawVisualizerIdle();
  blitRoll();
}

function seekTo(sec) {
  sec = Math.max(0, Math.min(state.buffer.duration - 0.01, sec));
  state.offset = sec;
  if (state.playing) startSource(sec);
  updateProgressUI(sec, state.buffer.duration);
}

function position() {
  if (!state.playing || !state.audioCtx) return state.offset;
  return state.audioCtx.currentTime - state.startedAt;
}

function tick() {
  if (!state.playing) {
    blitRoll();
    return;
  }
  const pos = position();
  if (!state.loop && state.buffer && pos >= state.buffer.duration) {
    stopPlayback(true);
    return;
  }
  updateProgressUI(pos, state.buffer.duration);
  drawVisualizer(pos);
  blitRoll();
  requestAnimationFrame(tick);
}

function updatePlayBtn() {
  $('playIcon').style.display = state.playing ? 'none' : 'block';
  $('pauseIcon').style.display = state.playing ? 'block' : 'none';
  document.body.classList.toggle('is-playing', state.playing);
}

function updateProgressUI(pos, dur) {
  const frac = dur ? (pos % dur) / dur : 0;
  $('progressFill').style.width = (frac * 100).toFixed(2) + '%';
  $('timeCur').textContent = fmtTime(pos);
  $('timeTot').textContent = fmtTime(dur);
}

function fmtTime(s) {
  s = Math.max(0, s || 0);
  const m = Math.floor(s / 60);
  const sec = Math.floor(s % 60);
  return `${m}:${String(sec).padStart(2, '0')}`;
}

// =====================================================================
// Download
// =====================================================================

function downloadWav() {
  if (!state.buffer) return;
  const comp = state.comp;
  const blob = audioBufferToWav(state.buffer);
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  const safeSeed = String(comp.seed).replace(/[^\w-]+/g, '_').slice(0, 32);
  a.download = `mybot_${comp.style}_${comp.bpm}bpm_${safeSeed}.wav`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 4000);
}

// =====================================================================
// Piano roll
// =====================================================================

const ROLL = { chordH: 20, drumLanes: 4, drumRowH: 11, pad: 2 };

function rollGeometry(comp) {
  const pitched = comp.events.filter((e) => e.track !== 'drums');
  let lo = 60, hi = 72;
  if (pitched.length) {
    lo = Math.min(...pitched.map((e) => e.midi)) - 1;
    hi = Math.max(...pitched.map((e) => e.midi)) + 1;
  }
  const rows = hi - lo + 1;
  return { lo, hi, rows };
}

function fitCanvas(cv) {
  const dpr = window.devicePixelRatio || 1;
  const rect = cv.getBoundingClientRect();
  cv.width = Math.max(1, Math.floor(rect.width * dpr));
  cv.height = Math.max(1, Math.floor(rect.height * dpr));
}

function drawRoll(comp) {
  const cv = state.rollCanvas;
  fitCanvas($('roll'));
  const cssW = $('roll').clientWidth;
  const cssH = $('roll').clientHeight;
  const dpr = window.devicePixelRatio || 1;
  cv.width = Math.floor(cssW * dpr);
  cv.height = Math.floor(cssH * dpr);
  const g = cv.getContext('2d');
  g.setTransform(dpr, 0, 0, dpr, 0, 0);

  const totalBeats = comp.totalBars * comp.beatsPerBar;
  const W = cssW, H = cssH;
  const drumH = ROLL.drumLanes * ROLL.drumRowH;
  const chordH = ROLL.chordH;
  const pitchH = H - chordH - drumH - ROLL.pad * 2;
  const { lo, rows } = rollGeometry(comp);
  const rowH = pitchH / rows;
  const x = (beat) => (beat / totalBeats) * W;

  // background
  g.fillStyle = '#0d1030';
  g.fillRect(0, 0, W, H);

  // grid
  for (let bar = 0; bar <= comp.totalBars; bar++) {
    const bx = x(bar * 4);
    g.fillStyle = bar % 4 === 0 ? 'rgba(255,255,255,0.14)' : 'rgba(255,255,255,0.06)';
    g.fillRect(bx, chordH, 1, H - chordH);
  }
  for (let beat = 0; beat <= totalBeats; beat++) {
    if (beat % 4 === 0) continue;
    g.fillStyle = 'rgba(255,255,255,0.03)';
    g.fillRect(x(beat), chordH, 1, pitchH);
  }
  // pitch rows
  for (let i = 0; i < rows; i++) {
    const m = lo + i;
    const isBlack = [1, 3, 6, 8, 10].includes(((m % 12) + 12) % 12);
    if (isBlack) {
      g.fillStyle = 'rgba(255,255,255,0.03)';
      g.fillRect(0, chordH + i * rowH, W, rowH);
    }
    if (((m % 12) + 12) % 12 === 0) {
      g.fillStyle = 'rgba(255,255,255,0.08)';
      g.fillRect(0, chordH + i * rowH + rowH, W, 1);
    }
  }

  // chords strip
  for (const ch of comp.chords) {
    const cx = x(ch.bar * 4);
    const cw = x(ch.bar * 4 + ch.bars * 4) - cx;
    g.fillStyle = 'rgba(139,92,246,0.16)';
    g.fillRect(cx, 0, cw, chordH);
    g.fillStyle = 'rgba(255,255,255,0.75)';
    g.font = '10px system-ui, sans-serif';
    g.textBaseline = 'middle';
    g.fillText(chordDisplayName(ch), cx + 4, chordH / 2);
  }
  // sections
  for (const sec of comp.sections) {
    const sx = x(sec.startBar * 4);
    g.fillStyle = 'rgba(34,211,238,0.9)';
    g.fillRect(sx, chordH - 2, 2, 6);
    g.fillStyle = 'rgba(34,211,238,0.75)';
    g.font = '9px system-ui, sans-serif';
    g.fillText(sec.name, sx + 5, chordH + 7);
  }

  // pitched notes
  for (const ev of comp.events) {
    if (ev.track === 'drums') continue;
    const nx = x(ev.t);
    const nw = Math.max(2, x(ev.t + ev.dur) - nx - 1);
    const ny = chordH + (hiRow(rows, lo, ev.midi)) * rowH;
    g.fillStyle = TRACK_COLORS[ev.track] || '#fff';
    g.globalAlpha = 0.45 + ev.vel * 0.55;
    g.fillRect(nx, ny + 1, nw, Math.max(2, rowH - 1.5));
    g.globalAlpha = 1;
  }

  // drum lanes
  const laneTop = chordH + pitchH + ROLL.pad;
  const laneOf = (midi) => {
    if (midi === DRUM.KICK) return 0;
    if (midi === DRUM.SNARE) return 1;
    if (midi === DRUM.HAT || midi === DRUM.OPENHAT) return 2;
    return 3;
  };
  const laneColors = ['#fb7185', '#f97316', '#facc15', '#e879f9'];
  const laneNames = ['kick', 'snare', 'hat', 'perc'];
  for (let l = 0; l < ROLL.drumLanes; l++) {
    g.fillStyle = 'rgba(255,255,255,0.03)';
    g.fillRect(0, laneTop + l * ROLL.drumRowH, W, ROLL.drumRowH - 1);
    g.fillStyle = 'rgba(255,255,255,0.25)';
    g.font = '8px system-ui, sans-serif';
    g.fillText(laneNames[l], 3, laneTop + l * ROLL.drumRowH + ROLL.drumRowH / 2);
  }
  for (const ev of comp.events) {
    if (ev.track !== 'drums') continue;
    const l = laneOf(ev.midi);
    const nx = x(ev.t);
    g.fillStyle = laneColors[l];
    g.globalAlpha = 0.35 + ev.vel * 0.6;
    g.fillRect(nx, laneTop + l * ROLL.drumRowH + 1, Math.max(2, ROLL.drumRowH * 0.7), ROLL.drumRowH - 3);
    g.globalAlpha = 1;
  }
}

function hiRow(rows, lo, midi) {
  return rows - 1 - (midi - lo);
}

function blitRoll() {
  const cv = $('roll');
  const g = cv.getContext('2d');
  g.clearRect(0, 0, cv.width, cv.height);
  g.drawImage(state.rollCanvas, 0, 0);
  // playhead
  if (state.comp && state.buffer) {
    const pos = state.playing ? position() : state.offset;
    const spb = 60 / state.comp.bpm;
    const beat = pos / spb;
    const totalBeats = state.comp.totalBars * state.comp.beatsPerBar;
    const frac = Math.max(0, Math.min(1, beat / totalBeats));
    const dpr = window.devicePixelRatio || 1;
    const cssW = cv.clientWidth;
    g.fillStyle = 'rgba(255,255,255,0.9)';
    g.fillRect(Math.round(frac * cssW * dpr), 0, Math.max(1, dpr), cv.height);
  }
}

// =====================================================================
// Visualiser
// =====================================================================

const visState = { freq: null, wave: null };

function drawVisualizer(pos) {
  const cv = $('vis');
  const g = cv.getContext('2d');
  const dpr = window.devicePixelRatio || 1;
  const W = cv.width, H = cv.height;
  g.clearRect(0, 0, W, H);

  if (!state.analyser || !state.playing) {
    drawVisualizerIdle();
    return;
  }
  const an = state.analyser;
  if (!visState.freq || visState.freq.length !== an.frequencyBinCount) {
    visState.freq = new Uint8Array(an.frequencyBinCount);
    visState.wave = new Uint8Array(an.fftSize);
  }
  an.getByteFrequencyData(visState.freq);
  an.getByteTimeDomainData(visState.wave);

  // spectrum bars
  const bars = 72;
  const grad = g.createLinearGradient(0, H, 0, 0);
  grad.addColorStop(0, 'rgba(139,92,246,0.95)');
  grad.addColorStop(0.55, 'rgba(56,189,248,0.9)');
  grad.addColorStop(1, 'rgba(232,121,249,0.95)');
  const bw = W / bars;
  for (let i = 0; i < bars; i++) {
    // log-ish mapping for nicer spectrum
    const idx = Math.floor(Math.pow(i / bars, 1.6) * (visState.freq.length * 0.7));
    const v = visState.freq[idx] / 255;
    const h = Math.max(2 * dpr, v * H * 0.9);
    g.fillStyle = grad;
    g.globalAlpha = 0.35 + v * 0.5;
    g.fillRect(i * bw + 1, H - h, bw - 2, h);
    g.globalAlpha = 1;
  }

  // waveform
  g.beginPath();
  for (let i = 0; i < visState.wave.length; i += 8) {
    const px = (i / (visState.wave.length - 1)) * W;
    const py = H / 2 + ((visState.wave[i] - 128) / 128) * (H * 0.32);
    if (i === 0) g.moveTo(px, py);
    else g.lineTo(px, py);
  }
  g.strokeStyle = 'rgba(255,255,255,0.75)';
  g.lineWidth = 1.5 * dpr;
  g.stroke();
}

function drawVisualizerIdle() {
  const cv = $('vis');
  const g = cv.getContext('2d');
  const dpr = window.devicePixelRatio || 1;
  const W = cv.width, H = cv.height;
  g.clearRect(0, 0, W, H);
  g.beginPath();
  g.moveTo(0, H / 2);
  g.lineTo(W, H / 2);
  g.strokeStyle = 'rgba(255,255,255,0.18)';
  g.lineWidth = 1 * dpr;
  g.stroke();
}

init();
