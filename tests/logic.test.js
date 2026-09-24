// Тесты ядра игры. Запуск: npm test  (или node --test tests/)
import test from 'node:test';
import assert from 'node:assert/strict';

import { CONFIG } from '../js/core/config.js';
import {
  ROOMS, CORRIDORS, TASKS, VENTS, FIX_STATIONS, EMERGENCY_PAD, SPAWNS,
  WORLD, reachableFrom, buildGraph, AREAS,
} from '../js/core/map.js';
import { makeRng } from '../js/core/rng.js';
import {
  assignTasks, tallyVotes, checkWin, taskProgressOfCrew, botVote, ejectText, aliveCounts, witnessesOf,
} from '../js/core/rules.js';
import { Sim, PHASE } from '../js/core/sim.js';

const mk = (seed = 42, settings = {}) => new Sim({ seed, settings: { botCount: 7, ...settings } });
const run = (sim, seconds, dt = 1 / 60) => {
  for (let t = 0; t < seconds; t += dt) sim.step(dt);
};

// ------------------------------------------------------------------ карта
test('карта связна: из Пруда можно дойти до любой комнаты', () => {
  const graph = buildGraph(AREAS);
  const reach = reachableFrom('pond', graph);
  for (const r of ROOMS) assert.ok(reach.has(r.id), `нет пути до ${r.id}`);
  for (const c of CORRIDORS) assert.ok(reach.has(c.id), `нет пути до ${c.id}`);
});

test('все важные точки стоят на проходимой зоне', () => {
  for (const t of TASKS) assert.ok(WORLD.canStand(t.x, t.y, CONFIG.playerRadius), `задание ${t.id} в стене`);
  for (const v of VENTS) assert.ok(WORLD.canStand(v.x, v.y, CONFIG.playerRadius), `нора ${v.id} в стене`);
  for (const f of FIX_STATIONS) assert.ok(WORLD.canStand(f.x, f.y, CONFIG.playerRadius), `станция ${f.id} в стене`);
  assert.ok(WORLD.canStand(EMERGENCY_PAD.x, EMERGENCY_PAD.y, CONFIG.playerRadius), 'кнопка сбора в стене');
  for (const s of SPAWNS) {
    assert.ok(
      WORLD.canStand(s.x + 14, s.y + 14, CONFIG.playerRadius) &&
        WORLD.canStand(s.x - 14, s.y - 14, CONFIG.playerRadius),
      `спавн ${s.x},${s.y} слишком близко к стене`,
    );
  }
});

test('норы ссылаются друг на друга и стоят в комнатах', () => {
  for (const v of VENTS) {
    const pair = WORLD.ventById(v.to);
    assert.ok(pair, `нет норы ${v.to}`);
    assert.equal(pair.to, v.id, `нора ${v.id} не симметрична`);
    assert.notEqual(v.id, v.to, 'нора не может вести сама в себя');
    assert.ok(WORLD.roomAt(v.x, v.y), `нора ${v.id} вне комнаты`);
  }
});

test('поиск пути ведёт через коридоры и заканчивается в цели', () => {
  const path = WORLD.findPath(300, 700, 1900, 200); // Пруд → Кладовая
  assert.ok(path.length > 2, 'маршрут слишком короткий');
  const last = path[path.length - 1];
  assert.deepEqual(last, { x: 1900, y: 200 });
  for (const p of path) assert.ok(WORLD.walkableAt(p.x, p.y), `точка ${p.x},${p.y} в стене`);
});

// ----------------------------------------------------------------- правила
test('задания раздаются без повторов и в нужном количестве', () => {
  const rng = makeRng(7);
  const players = [0, 1, 2].map((i) => ({ id: `p${i}`, role: 'crew' }));
  const map = assignTasks(players, TASKS, 5, rng);
  for (const p of players) {
    const list = map.get(p.id);
    assert.equal(list.length, 5);
    assert.equal(new Set(list.map((t) => t.id)).size, 5);
    assert.ok(list.every((t) => !t.done));
  }
});

test('подсчёт голосов: победитель, ничья и пропуск', () => {
  const alive = ['a', 'b', 'c', 'd'];
  const win = tallyVotes(new Map([['a', 'b'], ['b', 'b'], ['c', null], ['d', 'a']]), alive);
  assert.equal(win.ejectedId, 'b');
  assert.equal(win.counts.get('b'), 2);
  assert.equal(win.skip, 1);

  const tie = tallyVotes(new Map([['a', 'b'], ['b', 'c'], ['c', null], ['d', null]]), alive);
  assert.equal(tie.ejectedId, null);
  assert.equal(tie.tie, true);

  const skipped = tallyVotes(new Map([['a', null], ['b', null], ['c', 'd'], ['d', 'c']]), alive);
  assert.equal(skipped.ejectedId, null, 'пропуск не должен никого выбрасывать');
});

test('условия победы', () => {
  const crew = (n) => Array.from({ length: n }, (_, i) => ({ id: `c${i}`, role: 'crew', alive: true }));
  const imp = (n) => Array.from({ length: n }, (_, i) => ({ id: `i${i}`, role: 'impostor', alive: true }));
  const tasks = { done: 0, total: 5, ratio: 0 };

  assert.equal(checkWin([...crew(3), ...imp(1).map((i) => ({ ...i, alive: false }))], tasks).winner, 'crew');
  assert.equal(checkWin([...crew(1), ...imp(1)], tasks).winner, 'impostor');
  assert.equal(checkWin([...crew(3), ...imp(1)], { done: 5, total: 5, ratio: 1 }).winner, 'crew');
  assert.equal(checkWin([...crew(3), ...imp(1)], tasks).over, false);
});

test('botVote голосует за увиденного убийцу и не голосует за себя', () => {
  const rng = makeRng(3);
  const alive = [{ id: 'a' }, { id: 'b' }, { id: 'c' }];
  const bot = { id: 'a' };
  const withMemory = botVote(bot, alive, { sawKill: new Set(['c']), nearBody: new Set() }, rng);
  assert.equal(withMemory, 'c');
  for (let i = 0; i < 60; i++) {
    const v = botVote(bot, alive, {}, rng);
    assert.notEqual(v, 'a');
  }
});

test('ejectText честно сообщает роль выброшенного', () => {
  assert.match(ejectText({ name: 'Квакс', role: 'impostor' }, 0), /был самозванцем/);
  assert.match(ejectText({ name: 'Пруди', role: 'crew' }, 1), /не был самозванцем/);
});

// -------------------------------------------------------------- симуляция
test('боты расходятся по карте и выполняют задания', () => {
  const sim = mk(11);
  const before = sim.players.map((p) => ({ x: p.x, y: p.y }));
  run(sim, 30);
  const moved = sim.players.filter((p, i) => Math.hypot(p.x - before[i].x, p.y - before[i].y) > 30);
  assert.ok(moved.length >= 5, `сдвинулось только ${moved.length} из ${sim.players.length}`);
  const progress = sim.crewTaskProgress();
  assert.ok(progress.done > 0, 'за 30 секунд ни одно задание не выполнено');
  for (const p of sim.players) {
    assert.ok(WORLD.walkableAt(p.x, p.y) || !p.alive, `${p.name} застрял в стене`);
  }
});

test('человек не проходит сквозь стены', () => {
  const sim = mk(5);
  sim.input.dx = -1;
  sim.input.dy = -1;
  run(sim, 8);
  assert.ok(WORLD.canStand(sim.human.x, sim.human.y, CONFIG.playerRadius), 'игрок ушёл за стену');
  assert.ok(sim.human.x >= 0 && sim.human.x <= WORLD.width);
});

test('самозванец убивает жертву: труп, тик смерти и кулдаун', () => {
  const sim = mk(9, { humanRole: 'impostor', botCount: 5 });
  const killer = sim.human;
  assert.equal(killer.role, 'impostor');
  const victim = sim.players.find((p) => p.role === 'crew' && p.alive);

  killer.killCooldown = 0;
  killer.x = victim.x - 20;
  killer.y = victim.y;
  // убираем свидетелей подальше
  for (const p of sim.players) {
    if (p.id !== killer.id && p.id !== victim.id) {
      p.x = 1900;
      p.y = 200;
    }
  }
  const witnesses = witnessesOf(
    { killerId: killer.id, victimId: victim.id, x: victim.x, y: victim.y, killerIsImpostor: true },
    sim.players,
    CONFIG.botWitnessRange,
  );
  assert.equal(witnesses.length, 0);

  assert.equal(sim.humanKill(), true);
  assert.equal(victim.alive, false);
  assert.equal(sim.bodies.length, 1);
  assert.equal(sim.bodies[0].victimId, victim.id);
  assert.equal(killer.killCooldown, CONFIG.killCooldown);
  assert.equal(sim.humanKill(), false, 'во время кулдауна убить нельзя');
});

test('норы переносят самозванца в парную точку', () => {
  const sim = mk(13, { humanRole: 'impostor', botCount: 3 });
  const p = sim.human;
  const vent = VENTS[0];
  p.x = vent.x;
  p.y = vent.y;
  assert.equal(sim.humanVent(), true);
  assert.equal(p.vented, true);
  assert.equal(sim.humanVent(), true); // выход
  const target = WORLD.ventById(vent.to);
  assert.ok(Math.hypot(p.x - target.x, p.y - target.y) < 1, 'вылез не в той норе');
  assert.equal(p.vented, false);
});

test('саботаж «Туман» режет обзор и чинится рубильником', () => {
  const sim = mk(17, { humanRole: 'impostor', botCount: 3 });
  const crew = sim.players.find((p) => p.role === 'crew');
  assert.equal(sim.visionRadius(crew), CONFIG.vision);
  sim.sabotageCooldown = 0;
  assert.equal(sim.startSabotage('fog', sim.human), true);
  assert.equal(sim.visionRadius(crew), CONFIG.visionFogged);
  assert.equal(sim.visionRadius(sim.human), CONFIG.vision, 'самозванец не должен слепнуть');
  assert.equal(sim.fixSabotage('fog', crew), true);
  assert.equal(sim.visionRadius(crew), CONFIG.vision);
  assert.equal(sim.sabotage, null);
});

test('репорт трупа запускает собрание, голосование и выброс', () => {
  const sim = mk(21, { botCount: 6, impostors: 2 });
  const victim = sim.players.find((p) => p.role === 'crew' && !p.isHuman);
  const killer = sim.players.find((p) => p.role === 'impostor');
  killer.killCooldown = 0;
  killer.x = victim.x - 10;
  killer.y = victim.y;
  sim.kill(killer.id, victim.id);

  const reporter = sim.players.find((p) => p.alive && p.id !== killer.id);
  reporter.x = sim.bodies[0].x;
  reporter.y = sim.bodies[0].y;
  assert.equal(sim.reportBody(sim.bodies[0], reporter), true);
  assert.equal(sim.phase, PHASE.DISCUSSION);
  assert.equal(sim.reportBody(sim.bodies[0], reporter), false, 'труп уже заявлен');

  sim.skipDiscussion();
  assert.equal(sim.phase, PHASE.VOTING);

  // все голосуют за самозванца
  for (const p of sim.alivePlayers()) sim.votes.set(p.id, killer.id);
  run(sim, 0.1);
  assert.equal(sim.phase, PHASE.EJECTING);
  assert.equal(sim.ejectedId, killer.id);
  run(sim, CONFIG.ejectTime + 0.2);
  assert.equal(killer.alive, false);
  assert.equal(sim.phase, PHASE.PLAYING);
  assert.equal(sim.bodies.length, 0, 'после собрания трупы убраны');
});

test('кнопка на кувшинке собирает экстренное собрание с кулдауном', () => {
  const sim = mk(23, { botCount: 3 });
  sim.human.x = EMERGENCY_PAD.x;
  sim.human.y = EMERGENCY_PAD.y;
  sim.emergencyCooldown = 0;
  assert.equal(sim.humanEmergency(), true);
  assert.equal(sim.phase, PHASE.DISCUSSION);
  assert.equal(sim.meetingReason, 'emergency');
  assert.ok(sim.emergencyCooldown > 0);
});

test('завершённые задания приводят к победе мирных', () => {
  const sim = mk(31, { botCount: 4, humanRole: 'crew' });
  const crew = sim.players.filter((p) => p.role === 'crew');
  for (const p of crew) for (const t of p.tasks) t.done = true;
  sim.step(1 / 60);
  assert.equal(sim.phase, PHASE.ENDED);
  assert.equal(sim.winner, 'crew');
});

test('если самозванцев не меньше мирных — победа самозванцев', () => {
  const sim = mk(37, { botCount: 4, impostors: 2, humanRole: 'crew' });
  const crew = sim.players.filter((p) => p.role === 'crew');
  for (const p of crew.slice(0, crew.length - 1)) p.alive = false;
  sim.step(1 / 60);
  const counts = aliveCounts(sim.players);
  assert.ok(counts.crew <= counts.impostor, 'тест настроен неверно');
  assert.equal(sim.phase, PHASE.ENDED);
  assert.equal(sim.winner, 'impostor');
});

test('мирные задания считаются без бутафорских заданий самозванца', () => {
  const sim = mk(41, { botCount: 5, impostors: 2 });
  const crew = sim.players.filter((p) => p.role === 'crew');
  const imp = sim.players.filter((p) => p.role === 'impostor');
  for (const p of crew) for (const t of p.tasks) t.done = true;
  for (const p of imp) for (const t of p.tasks) t.done = true;
  const progress = taskProgressOfCrew(sim.players, sim.tasksMap());
  const crewTotal = crew.reduce((n, p) => n + p.tasks.length, 0);
  assert.equal(progress.total, crewTotal);
  assert.equal(progress.done, crewTotal);
  assert.equal(progress.ratio, 1);
});

test('мертвец становится призраком и видит дальше', () => {
  const sim = mk(47, { botCount: 3 });
  const dead = sim.players.find((p) => !p.isHuman && p.alive);
  dead.alive = false;
  assert.ok(sim.visionRadius(dead) > CONFIG.vision);
});

test('призрак доделывает задания, но не может репортить труп', () => {
  const sim = mk(61, { humanRole: 'crew' });
  sim.human.alive = false;

  const task = sim.human.tasks.find((t) => !t.done);
  const def = sim.world.taskById(task.id);
  sim.human.x = def.x;
  sim.human.y = def.y;
  sim.input.interact = true;
  run(sim, CONFIG.taskHoldTime + 0.5);
  sim.input.interact = false;
  assert.equal(task.done, true, 'призрак не смог доделать задание');

  // труп прямо под призраком — репортить он не имеет права
  const other = sim.players.find((p) => p.alive && !p.isHuman && p.role === 'crew');
  other.x = def.x + 5;
  other.y = def.y;
  const killer = sim.players.find((p) => p.role === 'impostor');
  killer.killCooldown = 0;
  killer.x = other.x - 8;
  killer.y = other.y;
  assert.equal(sim.kill(killer.id, other.id), true, 'убийство не засчиталось');
  assert.ok(sim.bodies.length >= 1);
  assert.equal(sim.actionContext().body, null, 'призрак видит труп для репорта');
  assert.equal(sim.humanReport(), false);
});

test('за 4 минуты полной симуляции игра приходит к какому-то исходу без падений', () => {
  for (const seed of [1, 2, 3, 4, 5]) {
    const sim = mk(seed, { botCount: 8, impostors: 1 });
    run(sim, 240);
    assert.ok(Object.values(PHASE).includes(sim.phase), 'неизвестная фаза');
    for (const p of sim.players) {
      if (p.alive) assert.ok(WORLD.walkableAt(p.x, p.y), `${p.name} в стене на сиде ${seed}`);
    }
  }
});
