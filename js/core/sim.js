// Ядро симуляции: сущности, движение, задания, убийства, норы, саботаж, собрания и голоса.
// Модуль не знает про DOM и canvas — его можно гонять в Node для тестов.

import { CONFIG, FROG_NAMES, SUITS } from './config.js';
import { makeRng } from './rng.js';
import { WORLD } from './map.js';
import {
  assignTasks,
  taskProgressOfCrew,
  tallyVotes,
  checkWin,
  witnessesOf,
  botVote,
  ejectText,
  aliveCounts,
} from './rules.js';

export const PHASE = {
  PLAYING: 'playing',
  DISCUSSION: 'discussion',
  VOTING: 'voting',
  EJECTING: 'ejecting',
  ENDED: 'ended',
};

let BODY_SEQ = 1;

export class Sim {
  constructor(opts = {}) {
    const seed = opts.seed ?? Math.floor(Math.random() * 1e9);
    this.rng = makeRng(seed);
    this.seed = this.rng.seed;
    this.world = opts.world || WORLD;
    this.hooks = opts.hooks || {};
    this.settings = {
      playerName: 'Вы',
      botCount: 9,
      impostors: 1,
      humanRole: 'random',
      tasksPerPlayer: CONFIG.tasksPerPlayer,
      ...(opts.settings || {}),
    };

    this.time = 0;
    this.phase = PHASE.PLAYING;
    this.phaseTimer = 0;
    this.meetingReason = null; // 'report' | 'emergency'
    this.reportedBody = null;
    this.votes = new Map();
    this.tally = null;
    this.ejectedId = null;
    this.ejectText = '';

    this.sabotage = null; // { type: 'fog' | 'comms', until }
    this.sabotageCooldown = 12;
    this.emergencyCooldown = CONFIG.emergencyCooldown;

    this.bodies = [];
    this.players = [];
    this.events = []; // короткий журнал для отладки/тестов

    this.input = { dx: 0, dy: 0, interact: false };
    this.pointer = { active: false, x: 0, y: 0 };

    this._setup();
  }

  // ---------------------------------------------------------------- setup
  _setup() {
    const total = 1 + this.settings.botCount;
    const names = this.rng.shuffle(FROG_NAMES).slice(0, total);
    const suits = this.rng.shuffle(SUITS).slice(0, total);
    const spawns = this.rng.shuffle(this.world.spawns);
    const count = Math.min(this.settings.impostors, total - 1);
    let impostorIds = this.rng.shuffle(Array.from({ length: total }, (_, i) => i)).slice(0, count);
    // Настройка humanRole нужна для отладки и тестов ('random' по умолчанию).
    if (this.settings.humanRole === 'impostor' && !impostorIds.includes(0)) {
      impostorIds = [0, ...impostorIds.filter((i) => i !== 0)].slice(0, Math.max(count, 1));
    } else if (this.settings.humanRole === 'crew' && impostorIds.includes(0)) {
      impostorIds = impostorIds.filter((i) => i !== 0);
      if (!impostorIds.length && total > 1) impostorIds = [1];
    }

    for (let i = 0; i < total; i++) {
      const spawn = spawns[i % spawns.length];
      const isImpostor = impostorIds.includes(i);
      const player = {
        id: `p${i}`,
        name: i === 0 ? this.settings.playerName || 'Вы' : names[i] || `Лягушка ${i}`,
        suit: suits[i] || SUITS[i % SUITS.length],
        role: isImpostor ? 'impostor' : 'crew',
        isHuman: i === 0,
        x: spawn.x + this.rng.range(-14, 14),
        y: spawn.y + this.rng.range(-14, 14),
        dir: 1,
        alive: true,
        vented: false,
        ventTimer: 0,
        killCooldown: isImpostor ? 10 : 0,
        walk: 0,
        tasks: [],
        bot: null,
      };
      if (!player.isHuman) {
        player.bot = {
          mode: 'task',
          path: [],
          pathIdx: 0,
          workTimer: 0,
          workTaskId: null,
          think: this.rng.range(0, CONFIG.botThink),
          wanderUntil: 0,
          voteAt: 0,
          memory: { sawKill: new Set(), nearBody: new Set() },
          targetBodyId: null,
        };
      }
      this.players.push(player);
    }

    const tasksByPlayer = assignTasks(this.players, this.world.tasks, this.settings.tasksPerPlayer, this.rng);
    for (const p of this.players) p.tasks = tasksByPlayer.get(p.id);

    this.human = this.players[0];
    this.emit('setup', { players: this.players, impostors: impostorIds.length });
  }

  emit(type, payload) {
    this.events.push({ type, time: this.time, payload });
    if (this.events.length > 200) this.events.shift();
    const h = this.hooks[type];
    if (typeof h === 'function') h(payload, this);
  }

  // ------------------------------------------------------------- helpers
  alivePlayers() {
    return this.players.filter((p) => p.alive);
  }

  playerById(id) {
    return this.players.find((p) => p.id === id) || null;
  }

  crewTaskProgress() {
    return taskProgressOfCrew(this.players, this.tasksMap());
  }

  tasksMap() {
    const m = new Map();
    for (const p of this.players) m.set(p.id, p.tasks);
    return m;
  }

  isImpostor(p) {
    return p.role === 'impostor';
  }

  visionRadius(p) {
    if (!p.alive) return 700; // призраки видят почти всё
    if (this.sabotage && this.sabotage.type === 'fog' && !this.isImpostor(p)) return CONFIG.visionFogged;
    return CONFIG.vision;
  }

  /** Может ли наблюдатель видеть цель (норы и смерть скрывают). */
  canSee(observer, target) {
    if (!observer.alive) return true;
    if (observer === target) return true;
    if (!target.alive) return false;
    if (target.vented && !this.isImpostor(observer)) return false;
    const d = Math.hypot(observer.x - target.x, observer.y - target.y);
    return d <= this.visionRadius(observer) + 40;
  }

  // --------------------------------------------------------------- step
  step(dt) {
    dt = Math.max(0, Math.min(dt, 0.05));
    this.time += dt;

    if (this.phase === PHASE.PLAYING) this._stepPlaying(dt);
    else if (this.phase === PHASE.DISCUSSION || this.phase === PHASE.VOTING) this._stepMeeting(dt);
    else if (this.phase === PHASE.EJECTING) this._stepEject(dt);

    for (const p of this.players) if (p.killCooldown > 0) p.killCooldown = Math.max(0, p.killCooldown - dt);
    if (this.sabotageCooldown > 0) this.sabotageCooldown = Math.max(0, this.sabotageCooldown - dt);
    if (this.emergencyCooldown > 0) this.emergencyCooldown = Math.max(0, this.emergencyCooldown - dt);
    if (this.sabotage && this.time >= this.sabotage.until) {
      const type = this.sabotage.type;
      this.sabotage = null;
      this.emit('sabotageEnd', { type });
    }
  }

  _stepPlaying(dt) {
    for (const p of this.players) {
      if (p.vented) {
        p.ventTimer -= dt;
        if (p.ventTimer <= 0) this.exitVent(p);
      }
      if (!p.alive) {
        if (p.isHuman) {
          this._moveGhost(p, dt);
          if (this.input.interact) this._humanInteract(p, dt);
        }
        continue;
      }
      if (p.isHuman) this._stepHuman(p, dt);
      else this._stepBot(p, dt);
    }
    this._separate();
    this._checkEnd();
  }

  _moveGhost(p, dt) {
    const v = CONFIG.ghostSpeed * dt;
    p.x += this.input.dx * v;
    p.y += this.input.dy * v;
    p.x = Math.max(10, Math.min(this.world.width - 10, p.x));
    p.y = Math.max(10, Math.min(this.world.height - 10, p.y));
    if (this.input.dx) p.dir = this.input.dx > 0 ? 1 : -1;
    if (this.input.dx || this.input.dy) p.walk += dt * 9;
  }

  _stepHuman(p, dt) {
    let dx = this.input.dx;
    let dy = this.input.dy;
    if (this.pointer.active) {
      const vx = this.pointer.x - p.x;
      const vy = this.pointer.y - p.y;
      const d = Math.hypot(vx, vy);
      if (d > 12) {
        dx = vx / d;
        dy = vy / d;
      } else {
        dx = 0;
        dy = 0;
      }
    }
    const len = Math.hypot(dx, dy);
    if (len > 1) {
      dx /= len;
      dy /= len;
    }
    if (p.vented) {
      p.walk += dt * 2;
      return; // в норе не бегаем
    }
    if (len > 0.01) {
      this._movePlayer(p, dx * CONFIG.playerSpeed * dt, dy * CONFIG.playerSpeed * dt);
      if (dx) p.dir = dx > 0 ? 1 : -1;
      p.walk += dt * 10;
    } else {
      p.walk *= 0.9;
    }

    if (this.input.interact) this._humanInteract(p, dt);
  }

  _movePlayer(p, dx, dy) {
    const r = CONFIG.playerRadius;
    if (this.world.canStand(p.x + dx, p.y, r)) p.x += dx;
    if (this.world.canStand(p.x, p.y + dy, r)) p.y += dy;
  }

  _separate() {
    const list = this.players.filter((p) => p.alive && !p.vented);
    for (let i = 0; i < list.length; i++) {
      for (let j = i + 1; j < list.length; j++) {
        const a = list[i];
        const b = list[j];
        const dx = b.x - a.x;
        const dy = b.y - a.y;
        const d = Math.hypot(dx, dy);
        const min = CONFIG.playerRadius * 1.6;
        if (d > 0 && d < min) {
          const push = ((min - d) / 2) * 0.6;
          const nx = (dx / d) * push;
          const ny = (dy / d) * push;
          this._movePlayer(a, -nx, -ny);
          this._movePlayer(b, nx, ny);
        }
      }
    }
  }

  // ------------------------------------------------------- взаимодействия
  /** Контекст действий человека: что рядом и что можно нажать. */
  actionContext() {
    const p = this.human;
    const ctx = {
      task: null,
      body: null,
      vent: null,
      pad: null,
      fix: null,
      kill: null,
      room: this.world.roomNameAt(p.x, p.y),
    };
    if (this.phase !== PHASE.PLAYING) return ctx;

    const nextTask = p.tasks.find((t) => !t.done);
    if (nextTask) {
      const def = this.world.taskById(nextTask.id);
      const d = Math.hypot(def.x - p.x, def.y - p.y);
      if (d < 60) ctx.task = { def, task: nextTask, dist: d };
    }

    if (p.alive) {
      const nv = this.world.nearestVent(p.x, p.y);
      if (nv && nv.dist < CONFIG.ventRange) ctx.vent = nv;

      const pad = this.world.emergencyPad;
      const padD = Math.hypot(pad.x - p.x, pad.y - p.y);
      if (padD < CONFIG.emergencyRange) ctx.pad = { def: pad, dist: padD, ready: this.emergencyCooldown <= 0 };

      if (this.sabotage) {
        const st = this.world.fixStations.find((s) => s.fixes === this.sabotage.type);
        if (st) {
          const d = Math.hypot(st.x - p.x, st.y - p.y);
          if (d < 70) ctx.fix = { def: st, type: this.sabotage.type, dist: d };
        }
      }
      if (this.isImpostor(p)) {
        const target = this._nearestVictim(p, CONFIG.killRange);
        if (target) ctx.kill = { target, ready: p.killCooldown <= 0 };
      }
    }

    let bestBody = null;
    let bestD = CONFIG.reportRange;
    for (const b of p.alive ? this.bodies : []) {
      if (b.reported) continue;
      const d = Math.hypot(b.x - p.x, b.y - p.y);
      if (d < bestD) {
        bestD = d;
        bestBody = b;
      }
    }
    ctx.body = bestBody;
    return ctx;
  }

  _nearestVictim(killer, range) {
    let best = null;
    let bestD = range;
    for (const p of this.players) {
      if (!p.alive || p.vented || this.isImpostor(p) || p.id === killer.id) continue;
      const d = Math.hypot(p.x - killer.x, p.y - killer.y);
      if (d < bestD) {
        bestD = d;
        best = p;
      }
    }
    return best;
  }

  _humanInteract(p, dt) {
    const ctx = this.actionContext();
    if (ctx.fix) {
      this._fixProgress = (this._fixProgress || 0) + dt;
      if (this._fixProgress >= CONFIG.fixHoldTime) {
        this._fixProgress = 0;
        this.fixSabotage(ctx.fix.type, p);
      }
      return;
    }
    this._fixProgress = 0;
    if (ctx.task) {
      const t = ctx.task.task;
      t.progress += dt;
      if (t.progress >= CONFIG.taskHoldTime) {
        t.progress = 0;
        t.done = true;
        this.emit('taskDone', { playerId: p.id, taskId: t.id, progress: this.crewTaskProgress() });
        this._checkEnd();
      }
    }
  }

  // ------------------------------------------------------------- действия
  kill(killerId, victimId) {
    const killer = this.playerById(killerId);
    const victim = this.playerById(victimId);
    if (!killer || !victim || !killer.alive || !victim.alive) return false;
    if (!this.isImpostor(killer) || this.isImpostor(victim)) return false;
    if (killer.killCooldown > 0 || this.phase !== PHASE.PLAYING) return false;
    if (Math.hypot(killer.x - victim.x, killer.y - victim.y) > CONFIG.killRange + 6) return false;

    victim.alive = false;
    victim.vented = false;
    victim.ventTimer = 0;
    killer.killCooldown = CONFIG.killCooldown;
    killer.vented = false;

    const body = {
      id: `b${BODY_SEQ++}`,
      victimId: victim.id,
      name: victim.name,
      suit: victim.suit,
      x: victim.x,
      y: victim.y,
      reported: false,
      room: this.world.roomNameAt(victim.x, victim.y),
    };
    this.bodies.push(body);

    const witnesses = witnessesOf(
      { killerId: killer.id, victimId: victim.id, x: body.x, y: body.y, killerIsImpostor: true },
      this.players,
      CONFIG.botWitnessRange,
    );
    for (const w of witnesses) {
      if (w.bot) w.bot.memory.sawKill.add(killer.id);
      if (w.isHuman) this.emit('sawKill', { killerId: killer.id, killerName: killer.name });
    }

    this.emit('kill', {
      killerId: killer.id,
      victimId: victim.id,
      bodyId: body.id,
      x: body.x,
      y: body.y,
      witnesses: witnesses.map((w) => w.id),
    });
    this._checkEnd();
    return true;
  }

  humanKill() {
    const ctx = this.actionContext();
    if (!ctx.kill || !ctx.kill.ready) return false;
    return this.kill(this.human.id, ctx.kill.target.id);
  }

  humanVent() {
    const p = this.human;
    if (!p.alive || !this.isImpostor(p)) return false;
    if (p.vented) {
      this.exitVent(p);
      return true;
    }
    const nv = this.world.nearestVent(p.x, p.y);
    if (!nv || nv.dist > CONFIG.ventRange) return false;
    this.enterVent(p, nv.vent);
    return true;
  }

  enterVent(p, vent) {
    p.vented = true;
    p.ventTimer = CONFIG.ventHideTime;
    p.ventId = vent.id;
    this.emit('vent', { playerId: p.id, ventId: vent.id, enter: true });
  }

  exitVent(p) {
    if (!p.vented) return;
    const vent = this.world.ventById(p.ventId);
    p.vented = false;
    p.ventTimer = 0;
    if (vent) {
      const target = this.world.ventById(vent.to);
      if (target && this.world.canStand(target.x, target.y, CONFIG.playerRadius)) {
        p.x = target.x;
        p.y = target.y;
      }
    }
    p.ventId = null;
    this.emit('vent', { playerId: p.id, enter: false });
  }

  /** Прыжок в нору и обратно без выхода наружу (для ботов). */
  ventTravel(p) {
    const vent = this.world.ventById(p.ventId);
    if (!vent) return false;
    const target = this.world.ventById(vent.to);
    if (!target) return false;
    p.x = target.x;
    p.y = target.y;
    p.ventId = target.id;
    this.emit('vent', { playerId: p.id, ventId: target.id, enter: false });
    return true;
  }

  humanReport() {
    const ctx = this.actionContext();
    if (!ctx.body) return false;
    return this.reportBody(ctx.body, this.human);
  }

  reportBody(body, reporter) {
    if (body.reported || this.phase !== PHASE.PLAYING) return false;
    body.reported = true;
    this.startMeeting('report', body, reporter);
    return true;
  }

  humanEmergency() {
    const ctx = this.actionContext();
    if (!ctx.pad || !ctx.pad.ready) return false;
    this.emergencyCooldown = CONFIG.emergencyCooldown;
    this.startMeeting('emergency', null, this.human);
    return true;
  }

  startSabotage(type, by) {
    if (by && !this.isImpostor(by)) return false;
    if (this.sabotage || this.sabotageCooldown > 0) return false;
    this.sabotage = { type, until: this.time + CONFIG.sabotageDuration };
    this.sabotageCooldown = CONFIG.sabotageCooldown;
    this.emit('sabotage', { type });
    return true;
  }

  humanSabotage(type = 'fog') {
    if (!this.isImpostor(this.human)) return false;
    return this.startSabotage(type, this.human);
  }

  fixSabotage(type, by) {
    if (!this.sabotage || this.sabotage.type !== type) return false;
    const t = this.sabotage.type;
    this.sabotage = null;
    this.emit('sabotageFixed', { type: t, by: by ? by.id : null });
    return true;
  }

  // --------------------------------------------------------------- боты
  _stepBot(p, dt) {
    const b = p.bot;
    b.think -= dt;
    if (b.think <= 0) {
      b.think = CONFIG.botThink;
      this._botThink(p);
    }

    if (b.mode === 'work') {
      b.workTimer -= dt;
      const task = p.tasks.find((t) => t.id === b.workTaskId);
      if (task) task.progress = Math.max(0, 1 - b.workTimer / CONFIG.taskHoldTime);
      if (b.workTimer <= 0) {
        if (task) {
          task.done = true;
          task.progress = 0;
          if (!this.isImpostor(p)) {
            this.emit('taskDone', { playerId: p.id, taskId: task.id, progress: this.crewTaskProgress() });
          }
          this._checkEnd();
        }
        b.mode = 'task';
        b.workTaskId = null;
      }
      return;
    }

    if (b.mode === 'fix') {
      const arrived = this._botWalk(p, dt);
      if (arrived) {
        b.fixTimer = (b.fixTimer || 0) + dt;
        if (b.fixTimer >= CONFIG.fixHoldTime) {
          b.fixTimer = 0;
          if (this.sabotage) this.fixSabotage(this.sabotage.type, p);
          b.mode = 'task';
        }
      } else {
        b.fixTimer = 0;
      }
      return;
    }

    if (b.mode === 'toBody') {
      const body = this.bodies.find((x) => x.id === b.targetBodyId);
      if (!body || body.reported) {
        b.mode = 'task';
        b.targetBodyId = null;
        return;
      }
      const arrived = this._botWalk(p, dt);
      const d = Math.hypot(body.x - p.x, body.y - p.y);
      if (d < CONFIG.reportRange) {
        this.reportBody(body, p);
        b.mode = 'task';
        b.targetBodyId = null;
        return;
      }
      if (arrived) {
        this._botSetDestination(p, body.x, body.y);
      }
      return;
    }

    if (b.mode === 'hunt') {
      const target = this.playerById(b.targetPlayerId);
      if (!target || !target.alive || target.vented || p.killCooldown > 0) {
        b.mode = 'task';
        b.targetPlayerId = null;
      } else {
        const d = Math.hypot(target.x - p.x, target.y - p.y);
        if (d <= CONFIG.killRange) {
          if (this.kill(p.id, target.id)) {
            b.mode = 'task';
            b.targetPlayerId = null;
            return;
          }
        }
        this._botWalkTo(p, dt, target.x, target.y, 20);
        return;
      }
    }

    if (b.mode === 'wander') {
      const arrived = this._botWalk(p, dt);
      if (arrived || this.time > b.wanderUntil) b.mode = 'task';
      return;
    }

    // mode === 'task'
    const next = p.tasks.find((t) => !t.done);
    if (!next) {
      b.mode = 'wander';
      this._botWander(p);
      this._botWalk(p, dt);
      return;
    }
    const def = this.world.taskById(next.id);
    const arrived = this._botWalkTo(p, dt, def.x, def.y, 40);
    if (arrived) {
      b.mode = 'work';
      b.workTaskId = next.id;
      b.workTimer = CONFIG.taskHoldTime * this.rng.range(0.85, 1.25);
    }
  }

  _botThink(p) {
    const b = p.bot;

    // Увидел труп — идёт репортить.
    for (const body of this.bodies) {
      if (body.reported) continue;
      const d = Math.hypot(body.x - p.x, body.y - p.y);
      if (d < CONFIG.botSeeBody && (b.mode !== 'toBody' || b.targetBodyId !== body.id)) {
        b.mode = 'toBody';
        b.targetBodyId = body.id;
        this._botSetDestination(p, body.x, body.y);
        return;
      }
    }

    // Самозванец ищет одинокую жертву.
    if (this.isImpostor(p) && p.killCooldown <= 0 && b.mode !== 'toBody') {
      const target = this._findPrey(p);
      if (target) {
        b.mode = 'hunt';
        b.targetPlayerId = target.id;
        return;
      }
    }

    // Мирные чинят саботаж.
    if (!this.isImpostor(p) && this.sabotage && b.mode === 'task' && this.rng.chance(0.25)) {
      const st = this.world.fixStations.find((s) => s.fixes === this.sabotage.type);
      if (st) {
        b.mode = 'fix';
        b.fixTimer = 0;
        this._botSetDestination(p, st.x, st.y);
        return;
      }
    }

    // Самозванец периодически мухлюет с саботажем.
    if (this.isImpostor(p) && !this.sabotage && this.sabotageCooldown <= 0 && this.rng.chance(0.12)) {
      this.startSabotage(this.rng.chance(0.5) ? 'fog' : 'comms', p);
    }

    // Иногда просто гуляем, чтобы не ходить по струнке.
    if (b.mode === 'task' && this.rng.chance(0.06)) {
      b.mode = 'wander';
      this._botWander(p);
    }
  }

  _findPrey(killer) {
    const candidates = this.players.filter((p) => {
      if (!p.alive || p.vented || this.isImpostor(p) || p.id === killer.id) return false;
      return Math.hypot(p.x - killer.x, p.y - killer.y) < 300;
    });
    if (!candidates.length) return null;
    for (const c of candidates) {
      const witnesses = this.players.filter((w) => {
        if (!w.alive || w.vented || w.id === c.id || w.id === killer.id) return false;
        if (this.isImpostor(w)) return false;
        return Math.hypot(w.x - c.x, w.y - c.y) < CONFIG.botWitnessRange;
      });
      if (!witnesses.length) return c;
    }
    return null;
  }

  _botWander(p) {
    const area = this.rng.pick(this.world.rooms);
    const pt = this.world.randomPointIn(area, this.rng, CONFIG.playerRadius);
    this._botSetDestination(p, pt.x, pt.y);
    p.bot.wanderUntil = this.time + this.rng.range(4, 9);
  }

  _botSetDestination(p, x, y) {
    p.bot.path = this.world.findPath(p.x, p.y, x, y);
    p.bot.pathIdx = 0;
  }

  /** Идти по маршруту; true — пришли. */
  _botWalk(p, dt) {
    const b = p.bot;
    if (!b.path.length) return true;
    if (b.pathIdx >= b.path.length) return true;
    const wp = b.path[b.pathIdx];
    const arrived = this._botWalkTo(p, dt, wp.x, wp.y, 14);
    if (arrived) {
      b.pathIdx += 1;
      return b.pathIdx >= b.path.length;
    }
    return false;
  }

  _botWalkTo(p, dt, tx, ty, stopDist) {
    const dx = tx - p.x;
    const dy = ty - p.y;
    const d = Math.hypot(dx, dy);
    if (d <= stopDist) return true;
    const step = CONFIG.playerSpeed * dt;
    this._movePlayer(p, (dx / d) * step, (dy / d) * step);
    if (dx) p.dir = dx > 0 ? 1 : -1;
    p.walk += dt * 10;
    return false;
  }

  // ----------------------------------------------------------- собрание
  startMeeting(reason, body, reporter) {
    if (this.phase !== PHASE.PLAYING) return false;
    this.phase = PHASE.DISCUSSION;
    this.phaseTimer = CONFIG.discussionTime;
    this.meetingReason = reason;
    this.reportedBody = body || null;
    this.votes = new Map();
    this.tally = null;
    this.ejectedId = null;
    for (const p of this.players) {
      if (p.vented) this.exitVent(p);
      p.walk = 0;
      if (p.bot) p.bot.voteAt = this.rng.range(1.2, CONFIG.votingTime - 2);
    }
    this.emit('meeting', {
      reason,
      body: body ? { name: body.name, room: body.room, suit: body.suit } : null,
      reporterId: reporter ? reporter.id : null,
    });
    return true;
  }

  castVote(voterId, targetId) {
    if (this.phase !== PHASE.VOTING) return false;
    const voter = this.playerById(voterId);
    if (!voter || !voter.alive || this.votes.has(voterId)) return false;
    if (targetId !== null && !this.playerById(targetId)?.alive) return false;
    this.votes.set(voterId, targetId);
    this.emit('vote', { voterId, targetId, votes: this.votes.size, total: this.alivePlayers().length });
    return true;
  }

  skipDiscussion() {
    if (this.phase === PHASE.DISCUSSION) this._startVoting();
  }

  _startVoting() {
    this.phase = PHASE.VOTING;
    this.phaseTimer = CONFIG.votingTime;
    this.votes = new Map();
    this.emit('phase', { phase: PHASE.VOTING });
  }

  _stepMeeting(dt) {
    this.phaseTimer -= dt;
    if (this.phase === PHASE.DISCUSSION) {
      if (this.phaseTimer <= 0) this._startVoting();
      return;
    }
    if (this.phase === PHASE.VOTING) {
      for (const p of this.alivePlayers()) {
        if (!p.bot || this.votes.has(p.id)) continue;
        if (this.phaseTimer <= CONFIG.votingTime - p.bot.voteAt) {
          const target = botVote(p, this.alivePlayers(), p.bot.memory, this.rng);
          this.castVote(p.id, target);
        }
      }
      const alive = this.alivePlayers();
      const allVoted = alive.every((p) => this.votes.has(p.id));
      if (allVoted || this.phaseTimer <= 0) this._finishVoting();
    }
  }

  _finishVoting() {
    const aliveIds = this.alivePlayers().map((p) => p.id);
    const tally = tallyVotes(this.votes, aliveIds);
    this.tally = tally;
    this.ejectedId = tally.ejectedId;
    this.phase = PHASE.EJECTING;
    this.phaseTimer = tally.ejectedId ? CONFIG.ejectTime : 2.6;
    const ejected = tally.ejectedId ? this.playerById(tally.ejectedId) : null;
    this.ejectText = ejected
      ? ejectText(ejected, aliveCounts(this.players).impostor - (this.isImpostor(ejected) ? 1 : 0))
      : 'Голоса разделились — никого не выбросили.';
    this.emit('ejectStart', {
      ejectedId: this.ejectedId,
      name: ejected ? ejected.name : null,
      suit: ejected ? ejected.suit : null,
      text: this.ejectText,
      counts: [...tally.counts.entries()],
      skip: tally.skip,
    });
  }

  _stepEject(dt) {
    this.phaseTimer -= dt;
    if (this.phaseTimer > 0) return;
    if (this.ejectedId) {
      const p = this.playerById(this.ejectedId);
      if (p && p.alive) {
        p.alive = false;
        p.vented = false;
      }
      this.emit('ejectEnd', { ejectedId: this.ejectedId });
    }
    this.ejectedId = null;
    this.votes = new Map();
    this.tally = null;
    this.bodies = []; // после собрания трупы убирают
    for (const p of this.players) p.killCooldown = Math.min(p.killCooldown, 12);
    if (this._checkEnd()) return;
    this.phase = PHASE.PLAYING;
    this.emit('phase', { phase: PHASE.PLAYING });
  }

  _checkEnd() {
    if (this.phase === PHASE.ENDED) return true;
    const result = checkWin(this.players, this.crewTaskProgress());
    if (!result.over) return false;
    this.phase = PHASE.ENDED;
    this.winner = result.winner;
    this.endReason = result.reason;
    this.emit('end', {
      winner: result.winner,
      reason: result.reason,
      impostors: this.players.filter((p) => p.role === 'impostor').map((p) => ({ id: p.id, name: p.name, suit: p.suit })),
      counts: aliveCounts(this.players),
    });
    return true;
  }
}

export default Sim;
