// Прогон клиентского кода (рендер + DOM) на поддельном браузере.
// Здесь исполняется настоящий renderer/ui/frog/main — браузерные API подменены.
import test from 'node:test';
import assert from 'node:assert/strict';

import { makeBrowser, INDEX_IDS } from './fakeBrowser.js';
import { CONFIG } from '../js/core/config.js';
import { PHASE } from '../js/core/sim.js';
import { EMERGENCY_PAD, VENTS } from '../js/core/map.js';

const browser = makeBrowser({ ids: INDEX_IDS });
globalThis.window = browser.window;
globalThis.document = browser.document;
globalThis.requestAnimationFrame = browser.window.requestAnimationFrame;
globalThis.cancelAnimationFrame = browser.window.cancelAnimationFrame;
globalThis.performance = browser.window.performance;

const { __game } = await import('../js/client/main.js');

const gameCanvas = browser.get('game');
const ctxCalls = () => gameCanvas.getContext('2d').callCount;

function newGame(seed = 777, settings = {}) {
  __game.startGame({ playerName: 'Тестер', botCount: 7, impostors: 1, tasksPerPlayer: 5, ...settings }, seed);
  browser.frames(2);
  return __game.getSim();
}

test('меню показывает живой пруд и рисует кадры', () => {
  assert.equal(__game.getMode(), 'menu');
  const before = ctxCalls();
  browser.frames(10);
  assert.ok(ctxCalls() - before > 500, 'рендер почти ничего не нарисовал');
  assert.ok(!browser.get('menu')._classes.has('hidden'), 'меню должно быть видно');
});

test('кнопка «В ПРУД!» запускает игру и показывает HUD', () => {
  browser.click('btn-start');
  assert.equal(__game.getMode(), 'game');
  assert.ok(!browser.get('hud')._classes.has('hidden'));
  const sim = __game.getSim();
  assert.equal(sim.players.length, 8);
  assert.equal(sim.human.name, 'Тестер');
  browser.frames(20);
  assert.ok(browser.get('task-list').children.length === 5, 'список заданий не построен');
  assert.match(browser.get('role-badge').textContent, /Самозванец|Мирная/);
});

test('клавиатура двигает лягушку, камера следит за ней', () => {
  const sim = newGame(5);
  const y0 = sim.human.y;
  browser.key('KeyW');
  browser.frames(40);
  browser.key('KeyW', 'keyup');
  assert.ok(sim.human.y < y0 - 20, `лягушка не пошла вверх: ${y0} -> ${sim.human.y}`);
  browser.frames(2);
});

test('зажатая мышь ведёт лягушку к курсору', () => {
  const sim = newGame(6);
  const x0 = sim.human.x;
  gameCanvas.dispatch('pointerdown', { clientX: 1200, clientY: 400 });
  browser.frames(30);
  gameCanvas.dispatch('pointerup');
  assert.notEqual(sim.human.x, x0, 'лягушка не сдвинулась за курсором');
  const frozen = sim.human.x;
  browser.frames(20);
  assert.equal(sim.human.x, frozen, 'после отпускания кнопки движение продолжается');
});

test('кнопки действий подсвечиваются у задания, норы и кувшинки', () => {
  const sim = newGame(11, { humanRole: 'impostor' });
  const task = sim.world.taskById(sim.human.tasks[0].id);
  sim.human.x = task.x;
  sim.human.y = task.y;
  browser.frames(2);
  assert.ok(browser.get('btn-use')._classes.has('ready'), 'кнопка задания не активна');

  const vent = VENTS[0];
  sim.human.x = vent.x;
  sim.human.y = vent.y;
  browser.frames(2);
  assert.ok(browser.get('btn-vent')._classes.has('ready'), 'кнопка норы не активна');

  sim.human.x = EMERGENCY_PAD.x;
  sim.human.y = EMERGENCY_PAD.y;
  sim.emergencyCooldown = 0;
  browser.frames(2);
  assert.ok(browser.get('btn-emergency')._classes.has('ready'), 'кнопка сбора не активна');
  browser.click('btn-emergency');
  assert.equal(sim.phase, PHASE.DISCUSSION);
  assert.equal(sim.meetingReason, 'emergency');
});

test('удержание «Использовать» выполняет задание', () => {
  const sim = newGame(12);
  const task = sim.human.tasks[0];
  const def = sim.world.taskById(task.id);
  sim.human.x = def.x;
  sim.human.y = def.y;
  browser.frames(1);
  browser.get('btn-use').dispatch('pointerdown');
  browser.frames(Math.ceil((CONFIG.taskHoldTime + 0.2) * 60));
  browser.get('btn-use').dispatch('pointerup');
  assert.equal(task.done, true, 'задание не выполнилось удержанием');
  assert.equal(sim.input.interact, false, 'кнопка залипла');
});

test('полный цикл: убийство → репорт → собрание → выброс', () => {
  const sim = newGame(21, { humanRole: 'impostor' });
  const victim = sim.players.find((p) => p.role === 'crew' && p.alive);
  sim.human.killCooldown = 0;
  sim.human.x = victim.x - 10;
  sim.human.y = victim.y;
  for (const p of sim.players) {
    if (p.id !== sim.human.id && p.id !== victim.id) {
      p.x = 1900;
      p.y = 200;
    }
  }
  browser.frames(2);
  assert.ok(browser.get('btn-kill')._classes.has('ready'), 'кнопка убийства не активна');
  browser.click('btn-kill');
  assert.equal(victim.alive, false);
  assert.equal(sim.bodies.length, 1);

  // репорт
  sim.human.x = sim.bodies[0].x;
  sim.human.y = sim.bodies[0].y;
  browser.frames(2);
  assert.ok(browser.get('btn-report')._classes.has('ready'), 'кнопка репорта не активна');
  browser.click('btn-report');
  assert.equal(sim.phase, PHASE.DISCUSSION);
  assert.ok(!browser.get('meeting')._classes.has('hidden'));
  const cards = browser.get('vote-grid').children;
  assert.equal(cards.length, sim.players.length + 1, 'карточек голосования не по числу игроков');

  // голосование
  sim.skipDiscussion();
  browser.frames(1);
  assert.equal(sim.phase, PHASE.VOTING);
  const crewCard = cards.find((c) => c.dataset.target && c.dataset.target !== sim.human.id && sim.playerById(c.dataset.target)?.alive);
  crewCard.dispatch('click');
  assert.equal(sim.votes.get(sim.human.id), crewCard.dataset.target);
  browser.frames(1);
  assert.ok(crewCard._classes.has('picked'), 'выбранный игрок не подсветился');

  // остальные голосуют за того же — его выбрасывают
  const targetId = crewCard.dataset.target;
  for (const p of sim.alivePlayers()) if (!sim.votes.has(p.id)) sim.votes.set(p.id, targetId);
  browser.frames(2);
  assert.equal(sim.phase, PHASE.EJECTING);
  assert.ok(!browser.get('eject')._classes.has('hidden'));
  assert.ok(browser.get('eject-text').textContent.length > 10);

  browser.frames(Math.ceil(CONFIG.ejectTime * 60) + 30);
  assert.equal(sim.playerById(targetId).alive, false);
  assert.ok(['playing', 'ended'].includes(sim.phase), `неожиданная фаза ${sim.phase}`);
  assert.ok(browser.get('meeting')._classes.has('hidden'), 'собрание не закрылось');
});

test('самозванец выигрывает, когда мирных не остаётся, — показывается финал', () => {
  const sim = newGame(33, { humanRole: 'impostor', botCount: 4 });
  const crew = sim.players.filter((p) => p.role === 'crew');
  for (const c of crew) {
    sim.human.killCooldown = 0;
    sim.human.x = c.x;
    sim.human.y = c.y;
    sim.kill(sim.human.id, c.id);
    if (sim.phase === PHASE.ENDED) break;
  }
  browser.frames(3);
  assert.equal(sim.phase, PHASE.ENDED);
  assert.ok(!browser.get('end')._classes.has('hidden'), 'экран финала не показан');
  assert.match(browser.get('end-title').textContent, /САМОВАНЦЫ|ПОБЕДА/);
  assert.ok(browser.get('end-impostors').children.length >= 1, 'нет карточек самозванцев');
  assert.match(browser.get('end-stats').innerHTML, /Заданий выполнено/);
});

test('саботаж показывает баннер, глушит задания и чинится', () => {
  const sim = newGame(44, { humanRole: 'impostor' });
  sim.sabotageCooldown = 0;
  browser.frames(1);
  browser.get('sabotage-menu').children[0].dispatch('click'); // туман
  assert.equal(sim.sabotage?.type, 'fog');
  browser.frames(2);
  assert.ok(!browser.get('sabotage-banner')._classes.has('hidden'));
  assert.match(browser.get('sabotage-banner').textContent, /Туман/);

  sim.fixSabotage('fog', sim.human);
  sim.sabotageCooldown = 0;
  browser.frames(1);
  browser.get('sabotage-menu').children[1].dispatch('click'); // связь
  assert.equal(sim.sabotage?.type, 'comms');
  browser.frames(2);
  assert.match(browser.get('tasks-title').textContent, /глушится/);
  sim.fixSabotage('comms', sim.human);
  browser.frames(2);
  assert.ok(browser.get('sabotage-banner')._classes.has('hidden'));
  assert.equal(browser.get('tasks-title').textContent, 'Задания пруда');
});

test('смерть игрока: призрак летает, рендер и HUD не падают', () => {
  const sim = newGame(55, { humanRole: 'crew' });
  sim.human.alive = false;
  browser.key('KeyD');
  const x0 = sim.human.x;
  browser.frames(60);
  browser.key('KeyD', 'keyup');
  assert.ok(sim.human.x > x0, 'призрак не двигается');
  assert.ok(!browser.get('hud')._classes.has('hidden'));

  // призрак доделывает задания кнопкой «Использовать»
  const task = sim.human.tasks.find((t) => !t.done);
  const def = sim.world.taskById(task.id);
  sim.human.x = def.x;
  sim.human.y = def.y;
  browser.frames(1);
  assert.ok(browser.get('btn-use')._classes.has('ready'), 'у призрака нет кнопки задания');
  browser.get('btn-use').dispatch('pointerdown');
  browser.frames(Math.ceil((CONFIG.taskHoldTime + 0.2) * 60));
  browser.get('btn-use').dispatch('pointerup');
  assert.equal(task.done, true, 'призрак не доделал задание');
});

test('пауза останавливает симуляцию и открывается по Esc', () => {
  const sim = newGame(66);
  browser.key('Escape');
  assert.equal(__game.isPaused(), true);
  const t = sim.time;
  browser.frames(30);
  assert.equal(sim.time, t, 'время идёт во время паузы');
  browser.click('btn-resume');
  assert.equal(__game.isPaused(), false);
  browser.frames(10);
  assert.ok(sim.time > t, 'после паузы игра не пошла');
});

test('возврат в меню и повторный старт', () => {
  newGame(77);
  browser.click('btn-menu');
  assert.equal(__game.getMode(), 'menu');
  browser.frames(5);
  browser.click('btn-start');
  assert.equal(__game.getMode(), 'game');
  browser.frames(10);
});

test('долгая игра без единой ошибки рисования (60 секунд симуляции)', () => {
  const sim = newGame(88, { botCount: 9, impostors: 2 });
  const before = ctxCalls();
  browser.frames(60 * 30, 1 / 30);
  assert.ok(ctxCalls() - before > 10000, 'слишком мало отрисовок');
  assert.ok(sim.time > 30);
});
