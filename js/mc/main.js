// main.js — демо «ИИ учится играть в Майнкрафт».
// Два мира на одном сиде: скрытый trainWorld для быстрого Q-learning
// и видимый viewWorld, на котором «играет» текущая жадная политика.

import { World, hashString, BLOCK_NAME } from './world.js';
import { MCAgent, ACTION_COUNT, ACTION_LABELS, ACTION_NAMES } from './agent.js';
import { Renderer } from './renderer.js';

const WORLD_W = 64;
const WORLD_H = 15;

// --- гиперпараметры обучения ---
const CONF = {
  alpha: 0.3,     // скорость обучения
  gamma: 0.99,    // дисконт будущей награды
  epsStart: 0.9,  // доля случайных действий в начале
  epsEnd: 0.02,
  epsDecay: 0.99, // затухание ε на эпизоде
  batch: 12,      // шагов обучения за кадр анимации
};

const $ = (id) => document.getElementById(id);

const params = new URLSearchParams(location.search);
const seedVal = params.get('seed') || String((Math.random() * 1e9) | 0);
const seedNum = hashString(seedVal);
const speed0 = Math.max(1, Math.min(40, Number(params.get('speed') || 3) || 3));

// обучение идёт на этом мире невидимо
let trainWorld = new World(WORLD_W, WORLD_H, seedNum);
// на этом мире агент «играет» на экране
let viewWorld = new World(WORLD_W, WORLD_H, seedNum);

const agent = new MCAgent();
const renderer = new Renderer($('world'));
const chartCtx = $('chart').getContext('2d');
const heatCtx = $('heat').getContext('2d');

// размеры графиков в CSS-пикселях (обновляются при ресайзе)
let chartW = 640, chartH = 160, heatW = 640, heatH = 170;

function sizeScaled(cv) {
  const dpr = Math.min(2, window.devicePixelRatio || 1);
  const w = cv.clientWidth || 640;
  const h = cv.clientHeight || 160;
  cv.width = Math.round(w * dpr);
  cv.height = Math.round(h * dpr);
  cv.getContext('2d').setTransform(dpr, 0, 0, dpr, 0, 0);
  return { w, h };
}

function refreshChartSize() {
  const c = sizeScaled($('chart'));
  chartW = c.w; chartH = c.h;
  const hh = sizeScaled($('heat'));
  heatW = hh.w; heatH = hh.h;
}

const els = {
  start: $('start'), pause: $('pause'), fast: $('fast'), agent: $('agent'), reset: $('reset'),
  seed: $('seed'), speed: $('speed'), speedLabel: $('speedLabel'),
  night: $('night'), showPath: $('showPath'), csv: $('csv'),
  stat: $('stat'), epsLab: $('epsLab'), agentMsg: $('agentMsg'),
};

let speed = speed0;
let running = false;
let paused = false;
let epsilon = CONF.epsStart;
let metrics = { episodes: 0, done: 0, steps: 0 };
let epLog = []; // {reward, steps, blocks, success}
let demoAcc = 0, lastT = 0;

// ============================ обучение (скрытый мир) ============================
function trainStep() {
  const s = trainWorld.getState();
  const a = agent.act(s, epsilon, Math.random);
  const { reward, done } = trainWorld.step(a);
  const s2 = trainWorld.getState();
  // Q(s,a) ← Q(s,a) + α·[ r + γ·max_a' Q(s',a') − Q(s,a) ]
  agent.learn(s, a, reward, s2, CONF.alpha, CONF.gamma);
  metrics.steps++;
  if (done) endEpisode();
}

function endEpisode() {
  metrics.episodes++;
  epLog.push({
    reward: Math.round(trainWorld.epReward * 10) / 10,
    steps: trainWorld.epSteps,
    blocks: trainWorld.collected,
    success: trainWorld.remaining() === 0,
  });
  if (epLog[epLog.length - 1].success) metrics.done++;
  epsilon = Math.max(CONF.epsEnd, epsilon * CONF.epsDecay);
  trainWorld.reset();
}

function runEpisodes(n) {
  let target = metrics.episodes + n;
  while (metrics.episodes < target) {
    trainStep();
  }
}

// ============================ демо (видимый мир) ============================
function demoStep() {
  const s = viewWorld.getState();
  const a = agent.bestAction(s);
  const hadBlock = a === 2 && viewWorld.blockAhead();
  const fxPre = viewWorld.agent.x + viewWorld.agent.dir;
  const { done } = viewWorld.step(a);
  if (hadBlock && !viewWorld.blockAhead()) renderer.markMined(fxPre, viewWorld.walkY);
  if (done) {
    viewWorld.reset();
    renderer.clearMarks();
  }
  return { a };
}

function policyMove() {
  const s = viewWorld.getState();
  const a = agent.bestAction(s);
  const hadBlock = a === 2 && viewWorld.blockAhead();
  const fxPre = viewWorld.agent.x + viewWorld.agent.dir;
  const { reward, done } = viewWorld.step(a);
  if (hadBlock && !viewWorld.blockAhead()) renderer.markMined(fxPre, viewWorld.walkY);
  if (done) { viewWorld.reset(); renderer.clearMarks(); }
  const n = viewWorld.nearest();
  const target = n ? `${BLOCK_NAME[n.kind]} ${n.x < viewWorld.agent.x ? '←' : '→'}${Math.abs(n.x - viewWorld.agent.x)}` : '—';
  let msg = `Ход политики: «${ACTION_NAMES[a]}» ${ACTION_LABELS[a]} (награда ${reward}) · ближайшая цель: ${target}`;
  if (done) msg += ' · мир зачищен!';
  els.agentMsg.textContent = msg;
  draw();
}

// ============================ цикл кадров ============================
function frame(t) {
  if (lastT === 0) lastT = t;
  const dt = Math.min(0.1, (t - lastT) / 1000);
  lastT = t;
  renderer.time = t / 1000;

  if (running && !paused) {
    for (let i = 0; i < speed * CONF.batch; i++) trainStep();
    // демо-агент шагает не быстрее, чем глаз успевает следить
    demoAcc += dt;
    const hz = Math.min(12, Math.max(3, speed * 2));
    const interval = 1 / hz;
    while (demoAcc >= interval) {
      demoAcc -= interval;
      demoStep();
    }
  }
  draw();
  requestAnimationFrame(frame);
}

function draw() {
  renderer.draw(viewWorld, els.night.checked, els.showPath.checked);
  drawChart();
  drawHeat();
  updateStatus();
}

function updateStatus() {
  const recent = epLog.slice(-10);
  const avg = recent.length ? recent.reduce((a, h) => a + h.reward, 0) / recent.length : 0;
  const last = epLog[epLog.length - 1];
  const phase = epsilon > 0.4 ? 'исследует' : epsilon > 0.1 ? 'уточняет стратегию' : 'действует оптимально';
  els.epsLab.textContent = `ε = ${epsilon.toFixed(3)} — ${phase} · скорость ×${speed}`;
  els.stat.innerHTML = [
    `эпизодов <b>${metrics.episodes}</b>`,
    `зачищено <b>${metrics.done}</b>`,
    `награда (ср.10) <b>${avg.toFixed(1)}</b>`,
    `посл. эпизод: <b>${last ? last.reward : '—'}</b> за ${last ? last.steps : '—'} шагов`,
    `демо собрало <b>${viewWorld.collected}/${viewWorld.total}</b>`,
    `состояний в таблице <b>${agent.stats.seen}</b>`,
  ].join('<br>');
}

// ============================ графики ============================
function drawChart() {
  chartCtx.clearRect(0, 0, chartW, chartH);
  const W = chartW, H = chartH;
  const n = epLog.length;
  if (n === 0) {
    chartCtx.fillStyle = '#5b6080';
    chartCtx.font = '12px monospace';
    chartCtx.fillText('награды появятся после первых эпизодов…', 10, H / 2);
    return;
  }
  const rewards = epLog.map((h) => h.reward);
  const min = Math.min(0, ...rewards);
  const max = Math.max(60, ...rewards);
  const span = max - min || 1;
  const N = Math.min(n, 220);
  const start = n - N;
  const sx = W / Math.max(1, N - 1);
  const yOf = (v) => H - 6 - ((v - min) / span) * (H - 16);

  chartCtx.strokeStyle = 'rgba(34,211,238,0.7)';
  chartCtx.lineWidth = 1.5;
  chartCtx.beginPath();
  const win = Math.min(7, n);
  for (let i = start; i < n; i++) {
    let s = 0, c = 0;
    for (let j = Math.max(0, i - win); j <= i; j++) { s += rewards[j]; c++; }
    const x = (i - start) * sx, y = yOf(s / c);
    if (i === start) chartCtx.moveTo(x, y); else chartCtx.lineTo(x, y);
  }
  chartCtx.stroke();

  for (let i = start; i < n; i++) {
    chartCtx.fillStyle = rewards[i] >= 0 ? '#8b5cf6' : '#fb7185';
    chartCtx.fillRect((i - start) * sx - 1, yOf(rewards[i]) - 1, 2, 2);
  }
  chartCtx.strokeStyle = 'rgba(255,255,255,0.14)';
  chartCtx.beginPath(); chartCtx.moveTo(0, yOf(0)); chartCtx.lineTo(W, yOf(0)); chartCtx.stroke();

  const succ = epLog.slice(start).filter((h) => h.success).length;
  chartCtx.fillStyle = '#34d399';
  chartCtx.font = '11px monospace';
  chartCtx.fillText(`полных зачисток в окне: ${succ}/${N}`, 8, 12);
}

function drawHeat() {
  heatCtx.clearRect(0, 0, heatW, heatH);
  const W = heatW, H = heatH;
  const cols = 7, rows = 2, labelH = 14;
  const gridTop = labelH, gridH = H - labelH - 20;
  const cellW = W / cols, cellH = gridH / rows;
  const colors = ['#22d3ee', '#a78bfa', '#34d399', '#fb7185'];

  let maxV = 1;
  for (const v of agent.visits.values()) maxV = Math.max(maxV, v);

  for (let sdx = -3; sdx <= 3; sdx++) {
    for (let inFront = 0; inFront <= 1; inFront++) {
      const state = { sdx, inFront };
      const key = agent.key(state);
      const q = agent.q.get(key);
      const visits = agent.visits.get(key) || 0;

      const x = (sdx + 3) * cellW;
      const y = gridTop + (inFront === 1 ? 0 : 1) * cellH;
      const w = cellW - 2, h = cellH - 2;

      heatCtx.fillStyle = `rgba(255,255,255,${0.05 + (visits / maxV) * 0.35})`;
      heatCtx.fillRect(x, y, w, h);

      if (q) {
        const total = Math.max(1, q[0] + q[1] + q[2] + q[3]);
        let acc = 0;
        for (let a = 0; a < ACTION_COUNT; a++) {
          const frac = q[a] / total;
          heatCtx.fillStyle = colors[a];
          heatCtx.fillRect(x + acc * w, y, Math.max(0, frac * w), h);
          acc += frac;
        }
        const best = ACTION_LABELS[agent.bestAction(state)];
        heatCtx.strokeStyle = 'rgba(255,255,255,0.8)';
        heatCtx.lineWidth = 1.5;
        heatCtx.strokeRect(x + 0.5, y + 0.5, w - 1, h - 1);
        heatCtx.fillStyle = '#fff';
        heatCtx.font = 'bold 10px monospace';
        heatCtx.fillText(best, x + 3, y + 10);
      }
    }
  }

  heatCtx.fillStyle = '#8a8fb0';
  heatCtx.font = '10px monospace';
  heatCtx.fillText('верхний ряд — перед агентом есть блок · нижний — путь свободен · по столбцам — где ближайший блок (−3…+3)', 4, 11);
  let lx = 4;
  for (let a = 0; a < ACTION_COUNT; a++) {
    heatCtx.fillStyle = colors[a];
    heatCtx.fillRect(lx, H - 14, 8, 8);
    heatCtx.fillStyle = '#cbd0f0';
    heatCtx.fillText(`${ACTION_LABELS[a]} ${ACTION_NAMES[a]}`, lx + 12, H - 6);
    lx += 96;
  }
}

// ============================ управление ============================
function setPaused(v) {
  paused = v;
  els.start.textContent = v ? '▶ Продолжить' : '⏸ Пауза';
}

function toggleStart() {
  if (!running) {
    running = true;
    setPaused(false);
    els.pause.disabled = false;
    els.agentMsg.textContent = 'Обучение запущено: в фоне агент пробует и ошибается, на экране — его текущая лучшая стратегия.';
  } else {
    setPaused(!paused);
  }
}

function resetAll() {
  running = false;
  paused = false;
  const sd = els.seed.value.trim() || String((Math.random() * 1e9) | 0);
  const sn = hashString(sd);
  trainWorld = new World(WORLD_W, WORLD_H, sn);
  viewWorld = new World(WORLD_W, WORLD_H, sn);
  agent.reset();
  renderer.clearMarks();
  epsilon = CONF.epsStart;
  metrics = { episodes: 0, done: 0, steps: 0 };
  epLog.length = 0;
  demoAcc = 0;
  const url = new URL(location.href);
  url.searchParams.set('seed', sd);
  url.searchParams.set('speed', speed);
  history.replaceState(null, '', url);
  els.start.textContent = '▶ Запустить обучение';
  els.pause.disabled = true;
  els.agentMsg.textContent = 'Мозг обнулён. Запускайте обучение — агент начнёт с нуля.';
  draw();
}

function wire() {
  els.start.onclick = toggleStart;
  els.pause.onclick = () => { if (running) setPaused(!paused); };
  els.fast.onclick = () => { runEpisodes(100); els.agentMsg.textContent = 'Прогнано 100 эпизодов обучения без анимации — смотрите график и тепловую карту.'; draw(); };
  els.agent.onclick = policyMove;
  els.reset.onclick = resetAll;
  els.seed.onchange = resetAll;
  els.speed.oninput = () => {
    speed = Number(els.speed.value);
    els.speedLabel.textContent = `×${speed}`;
    const url = new URL(location.href);
    url.searchParams.set('speed', speed);
    history.replaceState(null, '', url);
  };
  els.csv.onclick = () => {
    const rows = [['episode', 'steps', 'reward', 'blocks', 'success'],
      ...epLog.map((h, i) => [i, h.steps, h.reward, h.blocks, h.success ? 1 : 0])];
    const text = rows.map((r) => r.join(',')).join('\n');
    const name = `minecraft-ai-${seedVal.replace(/[^\w.-]/g, '_')}.csv`;
    if (typeof URL !== 'undefined' && URL.createObjectURL) {
      const blob = new Blob([text], { type: 'text/csv;charset=utf-8' });
      const a = document.createElement('a');
      a.href = URL.createObjectURL(blob);
      a.download = name;
      a.click();
      URL.revokeObjectURL(a.href);
    } else {
      const a = document.createElement('a');
      a.href = 'data:text/csv;charset=utf-8,' + encodeURIComponent(text);
      a.download = name;
      a.click();
    }
  };
  els.showPath.onchange = draw;
  els.night.onchange = draw;
}

// ============================ старт ============================
function init() {
  refreshChartSize();
  window.addEventListener('resize', () => { refreshChartSize(); draw(); });
  renderer.sizeTo(viewWorld);
  els.seed.value = seedVal;
  els.speed.value = String(speed);
  els.speedLabel.textContent = `×${speed}`;
  const url = new URL(location.href);
  if (!params.get('seed')) url.searchParams.set('seed', seedVal);
  url.searchParams.set('speed', speed);
  history.replaceState(null, '', url);
  wire();
  requestAnimationFrame(frame);
  draw();
}

init();
