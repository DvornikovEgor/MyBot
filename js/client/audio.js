// Простой синтезатор на WebAudio — никаких внешних файлов.
let ctx = null;
let enabled = true;

function ac() {
  if (!enabled) return null;
  if (!ctx) {
    const AC = window.AudioContext || window.webkitAudioContext;
    if (!AC) return null;
    ctx = new AC();
  }
  if (ctx.state === 'suspended') ctx.resume();
  return ctx;
}

function tone({ freq = 440, to = null, dur = 0.18, type = 'sine', gain = 0.15, delay = 0 }) {
  const a = ac();
  if (!a) return;
  const t0 = a.currentTime + delay;
  const osc = a.createOscillator();
  const g = a.createGain();
  osc.type = type;
  osc.frequency.setValueAtTime(freq, t0);
  if (to) osc.frequency.exponentialRampToValueAtTime(Math.max(30, to), t0 + dur);
  g.gain.setValueAtTime(0.0001, t0);
  g.gain.exponentialRampToValueAtTime(gain, t0 + 0.012);
  g.gain.exponentialRampToValueAtTime(0.0001, t0 + dur);
  osc.connect(g).connect(a.destination);
  osc.start(t0);
  osc.stop(t0 + dur + 0.02);
}

function noise({ dur = 0.3, gain = 0.12, filter = 900, delay = 0 }) {
  const a = ac();
  if (!a) return;
  const t0 = a.currentTime + delay;
  const len = Math.floor(a.sampleRate * dur);
  const buf = a.createBuffer(1, len, a.sampleRate);
  const data = buf.getChannelData(0);
  for (let i = 0; i < len; i++) data[i] = (Math.random() * 2 - 1) * (1 - i / len);
  const src = a.createBufferSource();
  src.buffer = buf;
  const bq = a.createBiquadFilter();
  bq.type = 'lowpass';
  bq.frequency.value = filter;
  const g = a.createGain();
  g.gain.value = gain;
  src.connect(bq).connect(g).connect(a.destination);
  src.start(t0);
}

export const sfx = {
  unlock() {
    ac();
  },
  setEnabled(v) {
    enabled = v;
  },
  kill() {
    tone({ freq: 220, to: 55, dur: 0.35, type: 'sawtooth', gain: 0.2 });
    noise({ dur: 0.28, gain: 0.14, filter: 600 });
  },
  report() {
    tone({ freq: 880, to: 620, dur: 0.16, type: 'square', gain: 0.13 });
    tone({ freq: 880, to: 620, dur: 0.16, type: 'square', gain: 0.13, delay: 0.22 });
  },
  meeting() {
    tone({ freq: 392, dur: 0.5, type: 'triangle', gain: 0.18 });
    tone({ freq: 523, dur: 0.5, type: 'triangle', gain: 0.14, delay: 0.08 });
  },
  vote() {
    tone({ freq: 660, to: 880, dur: 0.09, type: 'square', gain: 0.09 });
  },
  vent() {
    tone({ freq: 300, to: 900, dur: 0.14, type: 'sine', gain: 0.12 });
    noise({ dur: 0.16, gain: 0.08, filter: 1800 });
  },
  task() {
    tone({ freq: 740, dur: 0.1, type: 'sine', gain: 0.12 });
    tone({ freq: 990, dur: 0.16, type: 'sine', gain: 0.12, delay: 0.09 });
  },
  step() {
    noise({ dur: 0.06, gain: 0.03, filter: 500 });
  },
  sabotage() {
    tone({ freq: 150, to: 90, dur: 0.7, type: 'sawtooth', gain: 0.14 });
  },
  fix() {
    tone({ freq: 520, to: 780, dur: 0.22, type: 'triangle', gain: 0.12 });
  },
  eject() {
    tone({ freq: 700, to: 120, dur: 0.9, type: 'sine', gain: 0.16 });
    noise({ dur: 0.6, gain: 0.06, filter: 1200 });
  },
  win() {
    [523, 659, 784, 1046].forEach((f, i) => tone({ freq: f, dur: 0.35, type: 'triangle', gain: 0.15, delay: i * 0.13 }));
  },
  lose() {
    [392, 330, 262, 196].forEach((f, i) => tone({ freq: f, dur: 0.4, type: 'sawtooth', gain: 0.12, delay: i * 0.16 }));
  },
};
