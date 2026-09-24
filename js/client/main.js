// Точка входа: связывает симуляцию, отрисовку, DOM и ввод.
import { Sim, PHASE } from '../core/sim.js';
import { WORLD } from '../core/map.js';
import { Renderer } from './render.js';
import { UI } from './ui.js';
import { sfx } from './audio.js';

const canvas = document.getElementById('game');
const renderer = new Renderer(canvas, WORLD);
window.addEventListener('resize', () => renderer.resize());

let sim = null;
let mode = 'menu'; // menu | game
let paused = false;
let raf = 0;
let last = performance.now();
let startTime = 0;
const keys = new Set();

const ui = new UI({
  onStart: (settings) => startGame(settings),
  onMenu: () => toMenu(),
  onPause: (on) => setPause(on),
  onSound: (v) => sfx.setEnabled(v),
  onVote: (id) => {
    if (sim) sim.castVote(sim.human.id, id);
  },
  onSkip: () => {
    if (sim) sim.skipDiscussion();
  },
  onSabotage: (type) => {
    if (sim) sim.humanSabotage(type);
  },
  onAction: (act) => doAction(act),
});

// ---------------------------------------------------------------- запуск
function makeHooks() {
  return {
    meeting: (p) => {
      ui.openMeeting(sim, p);
      sfx.meeting();
      renderer.kick(6);
    },
    phase: (p) => {
      if (p.phase === PHASE.PLAYING) {
        ui.closeMeeting();
        ui.hideEject();
      }
    },
    ejectStart: (p) => {
      ui.closeMeeting();
      ui.showEject(sim, p);
      sfx.eject();
    },
    kill: (p) => {
      sfx.kill();
      renderer.kick(14);
      const human = sim.human;
      if (p.killerId === human.id) ui.toast(`Вы прикончили ${sim.playerById(p.victimId).name}. Делайте вид, что квакали по делу.`, 'danger');
      else if (p.victimId === human.id) ui.toast('Вас прикончили! Вы призрак: доделайте задания и летайте сквозь стены.', 'danger', 6000);
    },
    sawKill: (p) => {
      ui.toast(`Вы видели, как ${p.killerName} прикончил лягушку! Сообщите об этом на собрании.`, 'danger', 6500);
      sfx.report();
    },
    taskDone: (p) => {
      if (p.playerId === sim.human.id) {
        sfx.task();
        ui.toast('Задание выполнено 🪷', 'good', 1700);
      }
    },
    sabotage: (p) => {
      sfx.sabotage();
      ui.toast(p.type === 'fog' ? '🌫️ Пруд заволокло туманом!' : '📡 Квак-связь глушится!', 'danger', 3000);
    },
    sabotageFixed: () => {
      sfx.fix();
      ui.toast('Починено!', 'good', 1800);
    },
    vent: (p) => {
      if (p.playerId === sim.human.id) sfx.vent();
    },
    vote: () => sfx.vote(),
    end: (p) => {
      const secs = Math.round(sim.time);
      const kills = sim.events.filter((e) => e.type === 'kill').length;
      const prog = sim.crewTaskProgress();
      const stats =
        `Время в пруду: <b>${Math.floor(secs / 60)}:${String(secs % 60).padStart(2, '0')}</b><br>` +
        `Заданий выполнено: <b>${prog.done}/${prog.total}</b><br>` +
        `Убийств: <b>${kills}</b> · Выбросили: <b>${sim.events.filter((e) => e.type === 'ejectStart' && e.payload.ejectedId).length}</b>`;
      ui.showEnd(sim, p, stats);
      if (p.winner === 'crew') {
        const humanWin = sim.human.role === 'crew';
        if (humanWin) sfx.win();
        else sfx.lose();
      } else {
        const humanWin = sim.human.role === 'impostor';
        if (humanWin) sfx.win();
        else sfx.lose();
      }
    },
  };
}

function startGame(settings, seed) {
  sfx.unlock();
  sim = new Sim({ seed, settings, hooks: makeHooks() });
  mode = 'game';
  paused = false;
  startTime = performance.now();
  ui.showPause(sim, false);
  ui.hideEject();
  ui.closeMeeting();
  ui.showHud(sim.human);
  const partners = sim.players.filter((p) => p.role === 'impostor' && !p.isHuman);
  ui.showReveal(sim.human, partners, 3.2);
  ui.toast(sim.isImpostor(sim.human) ? 'Вы самозванец. Не палитесь!' : 'Найдите задания со стрелкой и выполняйте их (E).', 'good', 5000);
  renderer.resize();
}

function toMenu() {
  mode = 'menu';
  paused = false;
  sim = new Sim({ settings: { botCount: 9, impostors: 1, playerName: 'Квакс' }, hooks: {} });
  ui.toMenu();
}

function setPause(on) {
  if (mode !== 'game') return;
  paused = on;
  ui.showPause(sim, on);
}

// ----------------------------------------------------------------- ввод
window.addEventListener('keydown', (e) => {
  if (['ArrowUp', 'ArrowDown', 'ArrowLeft', 'ArrowRight', 'Space'].includes(e.code)) e.preventDefault();
  if (e.repeat) return;
  keys.add(e.code);
  if (mode !== 'game') return;
  switch (e.code) {
    case 'KeyR': doAction('report'); break;
    case 'KeyQ': doAction('kill'); break;
    case 'KeyV': doAction('vent'); break;
    case 'KeyG': doAction('emergency'); break;
    case 'KeyX': document.getElementById('sabotage-menu').classList.toggle('hidden'); break;
    case 'Digit1': doAction('sabotage-fog'); break;
    case 'Digit2': doAction('sabotage-comms'); break;
    case 'Escape': setPause(!paused); break;
    default: break;
  }
});
window.addEventListener('keyup', (e) => keys.delete(e.code));

canvas.addEventListener('pointerdown', (e) => {
  if (mode !== 'game') return;
  const rect = canvas.getBoundingClientRect();
  sim.pointer.active = true;
  const w = renderer.screenToWorld(e.clientX - rect.left, e.clientY - rect.top);
  sim.pointer.x = w.x;
  sim.pointer.y = w.y;
});
canvas.addEventListener('pointermove', (e) => {
  if (!sim || !sim.pointer.active) return;
  const rect = canvas.getBoundingClientRect();
  const w = renderer.screenToWorld(e.clientX - rect.left, e.clientY - rect.top);
  sim.pointer.x = w.x;
  sim.pointer.y = w.y;
});
for (const ev of ['pointerup', 'pointercancel', 'pointerleave']) {
  canvas.addEventListener(ev, () => {
    if (sim) sim.pointer.active = false;
  });
}

function doAction(act) {
  if (!sim || mode !== 'game' || paused) return;
  switch (act) {
    case 'use-start': setUse(true); break;
    case 'use-end': setUse(false); break;
    case 'report': sim.humanReport(); break;
    case 'kill': sim.humanKill(); break;
    case 'vent': sim.humanVent(); break;
    case 'emergency': sim.humanEmergency(); break;
    case 'sabotage-fog': sim.humanSabotage('fog'); break;
    case 'sabotage-comms': sim.humanSabotage('comms'); break;
    default: break;
  }
}

/** Удержание «Использовать» мышью/пальцем (клавиша E обрабатывается в readKeys). */
let useHeld = false;
function setUse(on) {
  useHeld = on;
  if (sim) sim.input.interact = on || keys.has('KeyE') || keys.has('Space');
}
for (const ev of ['pointerup', 'pointercancel']) {
  window.addEventListener(ev, () => {
    if (useHeld) setUse(false);
  });
}

function readKeys() {
  if (!sim) return;
  let dx = 0;
  let dy = 0;
  if (keys.has('KeyW') || keys.has('ArrowUp')) dy -= 1;
  if (keys.has('KeyS') || keys.has('ArrowDown')) dy += 1;
  if (keys.has('KeyA') || keys.has('ArrowLeft')) dx -= 1;
  if (keys.has('KeyD') || keys.has('ArrowRight')) dx += 1;
  const len = Math.hypot(dx, dy) || 1;
  sim.input.dx = dx / len;
  sim.input.dy = dy / len;
  if (!useHeld) sim.input.interact = keys.has('KeyE') || keys.has('Space');
}

// ----------------------------------------------------------------- цикл
function frame(now) {
  raf = requestAnimationFrame(frame);
  const dt = Math.min(0.05, Math.max(0, (now - last) / 1000));
  last = now;

  if (!sim) return;
  const playing = mode === 'game' && !paused && sim.phase !== PHASE.ENDED;

  if (playing) {
    readKeys();
    sim.step(dt);
  } else {
    sim.input.dx = 0;
    sim.input.dy = 0;
    sim.input.interact = false;
    if (mode === 'menu') sim.step(dt); // живой фон за меню
  }

  const follow = mode === 'menu' ? sim.players[1] : sim.human;
  renderer.draw(sim, playing || mode === 'menu' ? dt : 0, follow);

  if (mode === 'game') {
    ui.updateTasks(sim);
    ui.updateSabotage(sim);
    ui.updateActions(sim, sim.actionContext());
    if (sim.phase === PHASE.DISCUSSION || sim.phase === PHASE.VOTING) ui.updateMeeting(sim);
  }
}

// старт
toMenu();
raf = requestAnimationFrame(frame);

// Доступ для автотестов (в браузере не используется).
export const __game = {
  getSim: () => sim,
  getMode: () => mode,
  isPaused: () => paused,
  startGame,
  doAction,
  setPause,
  toMenu,
};
