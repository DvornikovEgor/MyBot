// Synth engine: renders a Composition to an AudioBuffer via OfflineAudioContext.
// Each style maps to instrument characters; drums are synthesised from scratch.

import { midiToFreq, DRUM } from './theory.js';
import { Rng, hashString } from './rng.js';

const SR = 44100;
const TAIL = 2.8; // seconds of reverb tail after the last beat

export async function renderComposition(comp) {
  const spb = 60 / comp.bpm;
  const durSec = comp.durationSec + TAIL;
  const ctx = new OfflineAudioContext(2, Math.ceil(durSec * SR), SR);
  const rng = new Rng(hashString(comp.seed + '/render'));

  // ---- master chain ------------------------------------------------------
  const master = ctx.createGain();
  master.gain.value = 0.82;
  const compressor = ctx.createDynamicsCompressor();
  compressor.threshold.value = -14;
  compressor.knee.value = 24;
  compressor.ratio.value = 3.5;
  compressor.attack.value = 0.005;
  compressor.release.value = 0.2;
  const clipper = ctx.createWaveShaper();
  clipper.curve = softClipCurve();
  master.connect(compressor).connect(clipper).connect(ctx.destination);

  // ---- fx sends ----------------------------------------------------------
  const reverbSend = ctx.createGain();
  reverbSend.gain.value = 1;
  const convolver = ctx.createConvolver();
  convolver.buffer = makeImpulse(ctx, comp.style, rng);
  const reverbReturn = ctx.createGain();
  reverbReturn.gain.value = (getStyleFx(comp).reverb.mix) * 1.6;
  reverbSend.connect(convolver).connect(reverbReturn).connect(master);

  const delaySend = ctx.createGain();
  delaySend.gain.value = 1;
  const dly = getStyleFx(comp).delay;
  const delayReturn = ctx.createGain();
  delayReturn.gain.value = dly.mix;
  if (dly.beats > 0) {
    const delay = ctx.createDelay(2);
    delay.delayTime.value = (dly.beats) * spb;
    const fb = ctx.createGain();
    fb.gain.value = dly.fb;
    const tone = ctx.createBiquadFilter();
    tone.type = 'lowpass';
    tone.frequency.value = 2600;
    delaySend.connect(delay);
    delay.connect(tone).connect(fb).connect(delay);
    tone.connect(delayReturn).connect(master);
  }

  // ---- sidechain ("duck") bus -------------------------------------------
  const duck = ctx.createGain();
  duck.gain.value = 1;
  duck.connect(master);
  const duckAmt = getStyleFx(comp).duck;

  const styles = {
    padBus: { out: duckAmt > 0 ? duck : master, rev: 0.5, dly: 0.05 },
    chordBus: { out: duckAmt > 0 ? duck : master, rev: 0.4, dly: 0.2 },
    bassBus: { out: duckAmt > 0 ? duck : master, rev: 0.05, dly: 0.02 },
    leadBus: { out: master, rev: 0.35, dly: 0.5 },
    arpBus: { out: master, rev: 0.3, dly: 0.4 },
    drumBus: { out: master, rev: 0.12, dly: 0 },
  };
  const bus = (spec) => {
    const g = ctx.createGain();
    g.gain.value = 1;
    g.connect(spec.out);
    const rs = ctx.createGain();
    rs.gain.value = spec.rev;
    g.connect(rs).connect(reverbSend);
    if (spec.dly > 0) {
      const ds = ctx.createGain();
      ds.gain.value = spec.dly;
      g.connect(ds).connect(delaySend);
    }
    return g;
  };
  const B = {
    pad: bus(styles.padBus),
    comp: bus(styles.chordBus),
    bass: bus(styles.bassBus),
    lead: bus(styles.leadBus),
    arp: bus(styles.arpBus),
    drums: bus(styles.drumBus),
  };

  // ---- shared noise ------------------------------------------------------
  const noiseBuf = makeNoise(ctx, 2, rng);

  // ---- style timbres -----------------------------------------------------
  const fx = getStyleFx(comp);
  const chip = comp.style === 'chiptune';
  const classic = comp.style === 'classical';
  const ambient = comp.style === 'ambient';

  const TIMBRE = {
    lead: chip
      ? { wave: 'square', detune: 0, filt: { f: 5200, q: 1, env: 0 }, amp: { a: 0.004, d: 0.05, s: 0.9, r: 0.04 }, gain: 0.16, vib: null }
      : classic
        ? { wave: 'triangle', detune: 3, filt: { f: 2400, q: 0.8, env: 700 }, amp: { a: 0.02, d: 0.3, s: 0.55, r: 0.25 }, gain: 0.2, vib: { rate: 5, depth: 5, delay: 0.25 } }
        : comp.style === 'synthwave'
          ? { wave: 'sawtooth', detune: 9, filt: { f: 900, q: 3, env: 2200 }, amp: { a: 0.01, d: 0.25, s: 0.6, r: 0.2 }, gain: 0.14, vib: { rate: 5.5, depth: 7, delay: 0.18 } }
          : comp.style === 'lofi'
            ? { wave: 'triangle', detune: 5, filt: { f: 1400, q: 1, env: 500 }, amp: { a: 0.01, d: 0.4, s: 0.5, r: 0.3 }, gain: 0.2, vib: { rate: 4.5, depth: 4, delay: 0.3 } }
            : comp.style === 'techno'
              ? { wave: 'sawtooth', detune: 12, filt: { f: 700, q: 6, env: 2600 }, amp: { a: 0.008, d: 0.18, s: 0.55, r: 0.12 }, gain: 0.13, vib: { rate: 6, depth: 6, delay: 0.15 } }
              : { wave: 'triangle', detune: 4, filt: { f: 1600, q: 1, env: 400 }, amp: { a: 0.02, d: 0.3, s: 0.5, r: 0.3 }, gain: 0.18, vib: { rate: 5, depth: 5, delay: 0.25 } },
  };

  // ---- schedule events ---------------------------------------------------
  const kicks = [];
  for (const ev of comp.events) {
    const t = ev.t * spb;
    const dur = ev.dur * spb;
    const vel = ev.vel;
    switch (ev.track) {
      case 'lead':
        leadVoice(ctx, B.lead, noiseBuf, t, dur, midiToFreq(ev.midi), vel, TIMBRE.lead, ev.pan ?? 0);
        break;
      case 'pad':
        padVoice(ctx, B.pad, t, dur, midiToFreq(ev.midi), vel, fx.pad, ev.pan ?? 0, comp.style);
        break;
      case 'comp':
        if (comp.style === 'lofi') epianoVoice(ctx, B.comp, t, dur, midiToFreq(ev.midi), vel, ev.pan ?? 0);
        else if (classic) pianoVoice(ctx, B.comp, t, dur, midiToFreq(ev.midi), vel, ev.pan ?? 0);
        else stabVoice(ctx, B.comp, t, dur, midiToFreq(ev.midi), vel, comp.style, ev.pan ?? 0);
        break;
      case 'bass':
        bassVoice(ctx, B.bass, t, dur, midiToFreq(ev.midi), vel, comp.style);
        break;
      case 'arp':
        arpVoice(ctx, B.arp, t, dur, midiToFreq(ev.midi), vel, chip, ev.pan ?? 0, ambient);
        break;
      case 'drums':
        if (ev.midi === DRUM.KICK) kicks.push(t);
        drumVoice(ctx, B.drums, noiseBuf, t, ev.midi, vel, chip, comp.style, rng);
        break;
    }
  }

  // ---- sidechain automation ---------------------------------------------
  if (duckAmt > 0 && kicks.length) {
    duck.gain.setValueAtTime(1 - duckAmt, 0);
    duck.gain.linearRampToValueAtTime(1, 0.05);
    for (const t of kicks) {
      duck.gain.setValueAtTime(1 - duckAmt, t + 0.005);
      duck.gain.linearRampToValueAtTime(1, Math.min(t + 0.28, durSec - 0.01));
    }
  }

  // ---- lo-fi vinyl noise -------------------------------------------------
  if (fx.vinyl) vinylNoise(ctx, master, noiseBuf, durSec, rng);

  return ctx.startRendering();
}

// =====================================================================
// Instruments
// =====================================================================

function env(g, t, { a, d, s, r }, peak, dur) {
  const hold = Math.max(a + d, dur);
  g.setValueAtTime(0.0001, t);
  g.exponentialRampToValueAtTime(Math.max(peak, 0.0002), t + a);
  g.exponentialRampToValueAtTime(Math.max(peak * s, 0.0002), t + a + d);
  g.setValueAtTime(Math.max(peak * s, 0.0002), t + hold);
  g.exponentialRampToValueAtTime(0.0001, t + hold + r);
  return t + hold + r + 0.02;
}

function panner(ctx, pan) {
  const p = ctx.createStereoPanner();
  p.pan.value = Math.max(-1, Math.min(1, pan));
  return p;
}

function oscs(ctx, out, freq, waves, detuneTotal) {
  const nodes = [];
  waves.forEach((w, i) => {
    const o = ctx.createOscillator();
    o.type = w;
    o.frequency.value = freq;
    const spread = waves.length > 1 ? (i / (waves.length - 1) - 0.5) * 2 : 0;
    o.detune.value = spread * detuneTotal;
    o.connect(out);
    nodes.push(o);
  });
  return nodes;
}

function leadVoice(ctx, out, noiseBuf, t, dur, freq, vel, p, pan) {
  const g = ctx.createGain();
  const pan_ = panner(ctx, pan);
  const filt = ctx.createBiquadFilter();
  filt.type = 'lowpass';
  filt.Q.value = p.filt.q;
  filt.frequency.setValueAtTime(Math.max(120, p.filt.f), t);
  filt.frequency.exponentialRampToValueAtTime(Math.max(120, p.filt.f + p.filt.env), t + 0.06);
  filt.frequency.exponentialRampToValueAtTime(Math.max(120, p.filt.f * 0.7), t + Math.max(dur, 0.25));
  g.connect(filt).connect(pan_).connect(out);

  const waves = p.wave === 'square' ? ['square'] : p.wave === 'sawtooth' ? ['sawtooth', 'sawtooth'] : ['triangle', 'triangle'];
  const list = oscs(ctx, g, freq, waves, p.detune || 6);

  let stopAt = env(g.gain, t, p.amp, p.gain * vel, dur);
  if (p.vib) {
    const lfo = ctx.createOscillator();
    lfo.type = 'sine';
    lfo.frequency.value = p.vib.rate;
    const lg = ctx.createGain();
    lg.gain.setValueAtTime(0.0001, t);
    lg.gain.setValueAtTime(0.0001, t + p.vib.delay);
    lg.gain.linearRampToValueAtTime(p.vib.depth, t + p.vib.delay + 0.25);
    lfo.connect(lg);
    for (const o of list) lg.connect(o.detune);
    lfo.start(t);
    lfo.stop(stopAt + 0.05);
  }
  for (const o of list) {
    o.start(t);
    o.stop(stopAt + 0.05);
  }
}

function epianoVoice(ctx, out, t, dur, freq, vel, pan) {
  // 2-operator FM: warm Rhodes-ish tone with a bell tine.
  const g = ctx.createGain();
  const pan_ = panner(ctx, pan * 0.7);
  g.connect(pan_).connect(out);

  const carrier = ctx.createOscillator();
  carrier.type = 'sine';
  carrier.frequency.value = freq;
  const tine = ctx.createOscillator();
  tine.type = 'sine';
  tine.frequency.value = freq * 3.02;
  const mod = ctx.createGain();
  mod.gain.setValueAtTime(freq * 2.2 * vel, t);
  mod.gain.exponentialRampToValueAtTime(freq * 0.15, t + 0.4);
  const tineGain = ctx.createGain();
  tineGain.gain.setValueAtTime(0.5 * vel, t);
  tineGain.gain.exponentialRampToValueAtTime(0.001, t + 0.18);
  tine.connect(tineGain).connect(g);
  mod.connect(carrier.frequency);
  carrier.connect(g);

  const stopAt = env(g.gain, t, { a: 0.004, d: 0.5, s: 0.25, r: 0.45 }, 0.3 * vel, dur);
  carrier.start(t); tine.start(t);
  carrier.stop(stopAt + 0.05); tine.stop(stopAt + 0.05);
}

function pianoVoice(ctx, out, t, dur, freq, vel, pan) {
  const g = ctx.createGain();
  const pan_ = panner(ctx, pan * 0.5);
  g.connect(pan_).connect(out);
  const harmonics = [[1, 1], [2, 0.32], [3, 0.12], [4, 0.06]];
  const list = [];
  for (const [mult, amp] of harmonics) {
    const o = ctx.createOscillator();
    o.type = 'sine';
    o.frequency.value = freq * mult * (1 + (mult > 1 ? 0.0004 * mult : 0));
    const hg = ctx.createGain();
    hg.gain.value = amp;
    o.connect(hg).connect(g);
    list.push(o);
    hg.gain.setValueAtTime(amp, t);
    hg.gain.exponentialRampToValueAtTime(Math.max(amp * 0.15, 0.0002), t + Math.min(1.2, dur + 0.5));
  }
  const stopAt = env(g.gain, t, { a: 0.003, d: 0.6, s: 0.2, r: 0.5 }, 0.22 * vel, dur);
  for (const o of list) { o.start(t); o.stop(stopAt + 0.05); }
}

function padVoice(ctx, out, t, dur, freq, vel, kind, pan, styleName) {
  const g = ctx.createGain();
  const pan_ = panner(ctx, pan);
  const filt = ctx.createBiquadFilter();
  filt.type = 'lowpass';
  filt.Q.value = kind === 'wide' ? 1.6 : 0.7;
  const base = kind === 'airy' ? 700 : kind === 'wide' ? 850 : kind === 'stabs' ? 1200 : 950;
  filt.frequency.setValueAtTime(Math.max(180, base * 0.6), t);
  filt.frequency.linearRampToValueAtTime(base, t + Math.max(0.5, dur * 0.5));
  g.connect(filt).connect(pan_).connect(out);

  const waves = kind === 'airy' ? ['triangle', 'triangle'] : kind === 'strings' ? ['sawtooth', 'sawtooth'] : kind === 'stabs' ? ['sawtooth', 'square'] : ['sawtooth', 'sawtooth'];
  const detune = kind === 'wide' ? 14 : 8;
  const list = oscs(ctx, g, freq, waves, detune);

  if (kind === 'strings') {
    const lfo = ctx.createOscillator();
    lfo.type = 'sine';
    lfo.frequency.value = 4.6;
    const lg = ctx.createGain();
    lg.gain.value = 4;
    lfo.connect(lg);
    for (const o of list) lg.connect(o.detune);
    lfo.start(t);
    lfo.stop(t + dur + 1.5);
  }

  const atk = kind === 'stabs' ? 0.01 : kind === 'airy' ? 1.1 : 0.35;
  const rel = kind === 'stabs' ? 0.1 : kind === 'airy' ? 1.3 : 0.7;
  const peak = (kind === 'stabs' ? 0.09 : 0.075) * vel * (styleName === 'ambient' ? 1.5 : 1);
  const stopAt = env(g.gain, t, { a: atk, d: 0.2, s: 0.85, r: rel }, peak, dur);
  for (const o of list) { o.start(t); o.stop(stopAt + 0.05); }
}

function stabVoice(ctx, out, t, dur, freq, vel, styleName, pan) {
  const g = ctx.createGain();
  const pan_ = panner(ctx, pan * 0.8);
  const filt = ctx.createBiquadFilter();
  filt.type = 'lowpass';
  filt.frequency.value = styleName === 'techno' ? 1800 : 2400;
  filt.Q.value = 2;
  g.connect(filt).connect(pan_).connect(out);
  const list = oscs(ctx, g, freq, ['sawtooth', 'sawtooth'], 10);
  const stopAt = env(g.gain, t, { a: 0.005, d: 0.12, s: 0.3, r: 0.12 }, 0.08 * vel, dur);
  for (const o of list) { o.start(t); o.stop(stopAt + 0.05); }
}

function bassVoice(ctx, out, t, dur, freq, vel, styleName) {
  const g = ctx.createGain();
  const filt = ctx.createBiquadFilter();
  filt.type = 'lowpass';
  const acid = styleName === 'techno';
  filt.Q.value = acid ? 8 : 1.2;
  const f0 = acid ? 240 : 350;
  filt.frequency.setValueAtTime(f0 + freq * 2, t);
  filt.frequency.exponentialRampToValueAtTime(Math.max(f0, freq * 1.4), t + (acid ? 0.12 : 0.3));
  g.connect(filt).connect(out);

  const o1 = ctx.createOscillator();
  o1.type = acid ? 'sawtooth' : styleName === 'chiptune' ? 'square' : 'sawtooth';
  o1.frequency.value = freq;
  const o2 = ctx.createOscillator();
  o2.type = 'sine';
  o2.frequency.value = freq; // sub
  const subG = ctx.createGain();
  subG.gain.value = 0.7;
  o2.connect(subG).connect(g);
  o1.connect(g);

  const peak = 0.2 * vel;
  const amp = styleName === 'ambient' ? { a: 0.15, d: 0.3, s: 0.8, r: 0.5 } : acid ? { a: 0.004, d: 0.1, s: 0.6, r: 0.06 } : { a: 0.006, d: 0.2, s: 0.55, r: 0.1 };
  const stopAt = env(g.gain, t, amp, peak, dur);
  o1.start(t); o2.start(t);
  o1.stop(stopAt + 0.05); o2.stop(stopAt + 0.05);
}

function arpVoice(ctx, out, t, dur, freq, vel, chip, pan, ambient) {
  const g = ctx.createGain();
  const pan_ = panner(ctx, pan);
  const filt = ctx.createBiquadFilter();
  filt.type = 'lowpass';
  filt.frequency.value = ambient ? 1800 : 3200;
  filt.Q.value = 1;
  g.connect(filt).connect(pan_).connect(out);
  const waves = chip ? ['square'] : ['sawtooth', 'triangle'];
  const list = oscs(ctx, g, freq, waves, chip ? 0 : 8);
  const amp = chip ? { a: 0.002, d: 0.06, s: 0.25, r: 0.03 } : ambient ? { a: 0.15, d: 0.4, s: 0.4, r: 0.5 } : { a: 0.003, d: 0.09, s: 0.2, r: 0.08 };
  const peak = (chip ? 0.09 : 0.075) * vel;
  const stopAt = env(g.gain, t, amp, peak, dur);
  for (const o of list) { o.start(t); o.stop(stopAt + 0.05); }
}

function drumVoice(ctx, out, noiseBuf, t, note, vel, chip, styleName, rng) {
  switch (note) {
    case DRUM.KICK: kick(ctx, out, t, vel, chip); break;
    case DRUM.SNARE: snare(ctx, out, noiseBuf, t, vel, chip, styleName, rng); break;
    case DRUM.CLAP:
    case DRUM.RIM: rim(ctx, out, noiseBuf, t, vel, rng); break;
    case DRUM.HAT: hat(ctx, out, noiseBuf, t, vel, false, chip, rng); break;
    case DRUM.OPENHAT: hat(ctx, out, noiseBuf, t, vel, true, chip, rng); break;
    case DRUM.TOM: tom(ctx, out, t, vel, 160); break;
    case DRUM.TOM2: tom(ctx, out, t, vel, 110); break;
  }
}

function kick(ctx, out, t, vel, chip) {
  const g = ctx.createGain();
  g.connect(out);
  const o = ctx.createOscillator();
  o.type = chip ? 'square' : 'sine';
  const f0 = chip ? 220 : 130;
  const f1 = chip ? 55 : 44;
  o.frequency.setValueAtTime(f0, t);
  o.frequency.exponentialRampToValueAtTime(f1, t + (chip ? 0.04 : 0.06));
  o.connect(g);
  g.gain.setValueAtTime(0.9 * vel, t);
  g.gain.exponentialRampToValueAtTime(0.001, t + (chip ? 0.12 : 0.3));
  o.start(t);
  o.stop(t + 0.35);

  if (!chip) {
    // transient click
    const cg = ctx.createGain();
    cg.gain.setValueAtTime(0.25 * vel, t);
    cg.gain.exponentialRampToValueAtTime(0.001, t + 0.02);
    const co = ctx.createOscillator();
    co.type = 'triangle';
    co.frequency.setValueAtTime(900, t);
    co.frequency.exponentialRampToValueAtTime(200, t + 0.02);
    co.connect(cg).connect(out);
    co.start(t);
    co.stop(t + 0.05);
  }
}

function snare(ctx, out, noiseBuf, t, vel, chip, styleName, rng) {
  const gated = styleName === 'synthwave';
  const dec = gated ? 0.28 : chip ? 0.08 : 0.16;
  // noise body
  const src = ctx.createBufferSource();
  src.buffer = noiseBuf;
  const bp = ctx.createBiquadFilter();
  bp.type = 'bandpass';
  bp.frequency.value = chip ? 3000 : 1900;
  bp.Q.value = 0.8;
  const ng = ctx.createGain();
  ng.gain.setValueAtTime(0.5 * vel, t);
  ng.gain.exponentialRampToValueAtTime(0.001, t + dec);
  src.connect(bp).connect(ng).connect(out);
  src.start(t, rng.next() * 1);
  src.stop(t + dec + 0.05);

  if (!chip) {
    // tonal shell
    for (const [f, a] of [[185, 0.35], [278, 0.22]]) {
      const o = ctx.createOscillator();
      o.type = 'triangle';
      o.frequency.setValueAtTime(f, t);
      o.frequency.exponentialRampToValueAtTime(f * 0.7, t + 0.1);
      const og = ctx.createGain();
      og.gain.setValueAtTime(a * vel, t);
      og.gain.exponentialRampToValueAtTime(0.001, t + dec * 0.8);
      o.connect(og).connect(out);
      o.start(t);
      o.stop(t + dec + 0.05);
    }
  }
}

function rim(ctx, out, noiseBuf, t, vel, rng) {
  const src = ctx.createBufferSource();
  src.buffer = noiseBuf;
  const hp = ctx.createBiquadFilter();
  hp.type = 'bandpass';
  hp.frequency.value = 2400;
  hp.Q.value = 1.5;
  const g = ctx.createGain();
  g.gain.setValueAtTime(0.3 * vel, t);
  g.gain.exponentialRampToValueAtTime(0.001, t + 0.05);
  src.connect(hp).connect(g).connect(out);
  src.start(t, 0.3 + rng.next() * 0.3);
  src.stop(t + 0.08);
}

function hat(ctx, out, noiseBuf, t, vel, open, chip, rng) {
  const src = ctx.createBufferSource();
  src.buffer = noiseBuf;
  const hp = ctx.createBiquadFilter();
  hp.type = 'highpass';
  hp.frequency.value = chip ? 5000 : 7500;
  const g = ctx.createGain();
  const dec = open ? 0.24 : chip ? 0.025 : 0.05;
  g.gain.setValueAtTime((open ? 0.22 : 0.16) * vel, t);
  g.gain.exponentialRampToValueAtTime(0.001, t + dec);
  src.connect(hp).connect(g).connect(out);
  src.start(t, rng.next() * 1);
  src.stop(t + dec + 0.03);
}

function tom(ctx, out, t, vel, f) {
  const o = ctx.createOscillator();
  o.type = 'sine';
  o.frequency.setValueAtTime(f * 1.6, t);
  o.frequency.exponentialRampToValueAtTime(f * 0.8, t + 0.15);
  const g = ctx.createGain();
  g.gain.setValueAtTime(0.35 * vel, t);
  g.gain.exponentialRampToValueAtTime(0.001, t + 0.18);
  o.connect(g).connect(out);
  o.start(t);
  o.stop(t + 0.25);
}

function vinylNoise(ctx, out, noiseBuf, durSec, rng) {
  const g = ctx.createGain();
  g.gain.value = 0.012;
  const lp = ctx.createBiquadFilter();
  lp.type = 'lowpass';
  lp.frequency.value = 5200;
  const hp = ctx.createBiquadFilter();
  hp.type = 'highpass';
  hp.frequency.value = 300;
  g.connect(hp).connect(lp).connect(out);

  const src = ctx.createBufferSource();
  src.buffer = noiseBuf;
  src.loop = true;
  src.connect(g);
  src.start(0);
  src.stop(durSec);

  // random crackles
  for (let t = rng.float(0.1, 0.5); t < durSec; t += rng.float(0.08, 0.6)) {
    const cg = ctx.createGain();
    cg.gain.setValueAtTime(rng.float(0.01, 0.05), t);
    cg.gain.exponentialRampToValueAtTime(0.0001, t + 0.01);
    const c = ctx.createBufferSource();
    c.buffer = noiseBuf;
    const cf = ctx.createBiquadFilter();
    cf.type = 'bandpass';
    cf.frequency.value = rng.float(1500, 4500);
    cf.Q.value = 2;
    c.connect(cf).connect(cg).connect(out);
    c.start(t, rng.next() * 1.5);
    c.stop(t + 0.02);
  }
}

// =====================================================================
// Utilities
// =====================================================================

function getStyleFx(comp) {
  // FX presets live with styles in theory; duplicate small defaults here to
  // keep engine self-contained for rendering params.
  const presets = {
    lofi:       { reverb: { mix: 0.16 }, delay: { beats: 0.75, fb: 0.22, mix: 0.10 }, duck: 0,     pad: 'soft',   vinyl: true },
    synthwave:  { reverb: { mix: 0.24 }, delay: { beats: 0.375, fb: 0.32, mix: 0.2 }, duck: 0.55,  pad: 'wide',   vinyl: false },
    ambient:    { reverb: { mix: 0.36 }, delay: { beats: 1.5, fb: 0.4, mix: 0.22 },   duck: 0,     pad: 'airy',   vinyl: false },
    techno:     { reverb: { mix: 0.12 }, delay: { beats: 0.25, fb: 0.26, mix: 0.12 }, duck: 0.6,   pad: 'stabs',  vinyl: false },
    chiptune:   { reverb: { mix: 0.06 }, delay: { beats: 0.25, fb: 0.18, mix: 0.08 }, duck: 0,     pad: null,     vinyl: false },
    classical:  { reverb: { mix: 0.26 }, delay: { beats: 0, fb: 0, mix: 0 },           duck: 0,     pad: 'strings', vinyl: false },
  };
  return presets[comp.style] || presets.lofi;
}

function makeNoise(ctx, seconds, rng) {
  const buf = ctx.createBuffer(1, Math.ceil(seconds * SR), SR);
  const d = buf.getChannelData(0);
  for (let i = 0; i < d.length; i++) d[i] = rng.next() * 2 - 1;
  return buf;
}

function makeImpulse(ctx, style, rng) {
  const size = { lofi: 1.4, synthwave: 2.6, ambient: 3.6, techno: 1.2, chiptune: 0.7, classical: 2.8 }[style] || 1.8;
  const len = Math.ceil(size * SR);
  const buf = ctx.createBuffer(2, len, SR);
  for (let ch = 0; ch < 2; ch++) {
    const d = buf.getChannelData(ch);
    let lp = 0;
    for (let i = 0; i < len; i++) {
      const t = i / len;
      const decay = Math.pow(1 - t, 2.2 + rng.next() * 0.3);
      lp = lp * 0.6 + (rng.next() * 2 - 1) * 0.4;
      d[i] = lp * decay;
    }
  }
  return buf;
}

function softClipCurve() {
  const n = 1024;
  const curve = new Float32Array(n);
  for (let i = 0; i < n; i++) {
    const x = (i / (n - 1)) * 2 - 1;
    curve[i] = Math.tanh(x * 1.5) * 0.92;
  }
  return curve;
}
