// Всё, что касается DOM: меню, HUD, собрание, выброс, финал.
import { CONFIG } from '../core/config.js';
import { PHASE } from '../core/sim.js';
import { drawFrogAvatar } from './frog.js';

const $ = (id) => document.getElementById(id);

export class UI {
  constructor(handlers) {
    this.h = handlers;
    this.el = {
      menu: $('menu'), reveal: $('reveal'), hud: $('hud'), meeting: $('meeting'),
      eject: $('eject'), pause: $('pause'), end: $('end'),
      menuFrog: $('menu-frog'), revealFrog: $('reveal-frog'), ejectFrog: $('eject-frog'),
      start: $('btn-start'), name: $('opt-name'), players: $('opt-players'),
      impostors: $('opt-impostors'), tasks: $('opt-tasks'),
      revealCard: $('reveal-card'), revealTitle: $('reveal-title'), revealText: $('reveal-text'),
      taskList: $('task-list'), taskBar: $('task-bar-fill'), tasksTitle: $('tasks-title'),
      roleBadge: $('role-badge'), sabotageBanner: $('sabotage-banner'),
      toastWrap: $('toast-wrap'),
      btnUse: $('btn-use'), btnReport: $('btn-report'), btnKill: $('btn-kill'),
      btnVent: $('btn-vent'), btnSabotage: $('btn-sabotage'), btnEmergency: $('btn-emergency'),
      sabotageMenu: $('sabotage-menu'), btnPause: $('btn-pause'),
      meetingTitle: $('meeting-title'), meetingSub: $('meeting-sub'),
      timerFill: $('meeting-timer-fill'), voteGrid: $('vote-grid'),
      voteStatus: $('vote-status'), btnSkip: $('btn-skip'),
      ejectText: $('eject-text'),
      endTitle: $('end-title'), endReason: $('end-reason'),
      endImpostors: $('end-impostors'), endStats: $('end-stats'),
      btnAgain: $('btn-again'), btnMenu: $('btn-menu'), btnResume: $('btn-resume'),
      btnQuit: $('btn-quit'), optSound: $('opt-sound'), pauseInfo: $('pause-info'),
    };
    this._menuAnim = 0;
    this._lastTasks = '';
    this._lastVotes = -1;
    this.bind();
  }

  bind() {
    this.el.start.addEventListener('click', () => this.h.onStart(this.settings()));
    this.el.btnAgain.addEventListener('click', () => this.h.onStart(this.settings()));
    this.el.btnMenu.addEventListener('click', () => this.h.onMenu());
    this.el.btnResume.addEventListener('click', () => this.h.onPause(false));
    this.el.btnQuit.addEventListener('click', () => this.h.onMenu());
    this.el.btnPause.addEventListener('click', () => this.h.onPause(true));
    this.el.optSound.addEventListener('change', (e) => this.h.onSound(e.target.checked));
    this.el.btnSkip.addEventListener('click', () => this.h.onSkip());
    for (const btn of this.el.sabotageMenu.querySelectorAll('button')) {
      btn.addEventListener('click', () => {
        this.h.onSabotage(btn.dataset.sab);
        this.el.sabotageMenu.classList.add('hidden');
      });
    }
    this.el.btnUse.addEventListener('pointerdown', (e) => {
      e.preventDefault();
      this.h.onAction('use-start');
    });
    for (const ev of ['pointerup', 'pointerleave', 'pointercancel']) {
      this.el.btnUse.addEventListener(ev, () => this.h.onAction('use-end'));
    }
    this.el.btnReport.addEventListener('click', () => this.h.onAction('report'));
    this.el.btnKill.addEventListener('click', () => this.h.onAction('kill'));
    this.el.btnVent.addEventListener('click', () => this.h.onAction('vent'));
    this.el.btnSabotage.addEventListener('click', () => this.el.sabotageMenu.classList.toggle('hidden'));
    this.el.btnEmergency.addEventListener('click', () => this.h.onAction('emergency'));
  }

  settings() {
    return {
      playerName: this.el.name.value.trim() || 'Квакс',
      botCount: parseInt(this.el.players.value, 10) - 1,
      impostors: parseInt(this.el.impostors.value, 10),
      tasksPerPlayer: parseInt(this.el.tasks.value, 10),
    };
  }

  show(id, on = true) {
    this.el[id].classList.toggle('hidden', !on);
  }

  toMenu() {
    for (const k of ['reveal', 'hud', 'meeting', 'eject', 'pause', 'end']) this.show(k, false);
    this.show('menu', true);
    this.animateMenuFrog();
  }

  // ------------------------------------------------------------- меню
  animateMenuFrog() {
    cancelAnimationFrame(this._menuAnim);
    const suits = [
      { body: '#4caf50', dark: '#2f7d33', belly: '#bfe8a8' },
      { body: '#e74c3c', dark: '#a5301f', belly: '#f6b8a8' },
    ];
    let i = 0;
    const loop = () => {
      if (this.el.menu.classList.contains('hidden')) return;
      i += 0.04;
      const suit = suits[Math.floor(i / 2) % 2];
      const ctx = this.el.menuFrog.getContext('2d');
      ctx.clearRect(0, 0, 150, 150);
      drawFrogAvatar(this.el.menuFrog, suit, { size: 150, t: i, walk: Math.sin(i * 3) * 2 });
      this._menuAnim = requestAnimationFrame(loop);
    };
    loop();
  }

  // ----------------------------------------------------------- роль
  showReveal(player, partners, seconds = 3) {
    const imp = player.role === 'impostor';
    this.el.revealCard.className = `reveal-card ${imp ? 'impostor' : 'crew'}`;
    this.el.revealTitle.textContent = imp ? 'ВЫ — САМОВАНЕЦ' : 'ВЫ — МИРНАЯ ЛЯГУШКА';
    this.el.revealText.textContent = imp
      ? `Притворяйтесь, что квакаете по делу. Убивайте поодиночке, прячьтесь в норах${
          partners.length ? `. Ваш напарник: ${partners.map((p) => p.name).join(', ')}` : ''
        }.`
      : 'Выполняйте задания пруда и вычислите, кто здесь переодетая жаба.';
    drawFrogAvatar(this.el.revealFrog, player.suit, { size: 180, t: 0 });
    this.show('reveal', true);
    setTimeout(() => this.show('reveal', false), seconds * 1000);
  }

  // ------------------------------------------------------------ HUD
  showHud(player) {
    this.show('menu', false);
    this.show('hud', true);
    const imp = player.role === 'impostor';
    this.el.roleBadge.className = imp ? 'impostor' : 'crew';
    this.el.roleBadge.textContent = imp ? 'Самозванец' : 'Мирная лягушка';
    for (const b of [this.el.btnKill, this.el.btnVent, this.el.btnSabotage]) {
      b.style.display = imp ? '' : 'none';
    }
    this._lastTasks = '';
  }

  updateTasks(sim) {
    const human = sim.human;
    const blocked = !!(sim.sabotage && sim.sabotage.type === 'comms');
    this.el.tasksTitle.textContent = blocked ? 'Квак-связь глушится…' : 'Задания пруда';
    const sig =
      (blocked ? 'B|' : '') + human.tasks.map((t) => `${t.id}:${t.done ? 1 : Math.floor(t.progress * 10)}`).join('|');
    if (sig === this._lastTasks) {
      // прогресс-бар всё равно обновляем (его двигают и боты)
      const p = sim.crewTaskProgress();
      this.el.taskBar.style.width = `${Math.round(p.ratio * 100)}%`;
      return;
    }
    this._lastTasks = sig;
    const p = sim.crewTaskProgress();
    this.el.taskBar.style.width = `${Math.round(p.ratio * 100)}%`;
    const next = human.tasks.find((t) => !t.done);
    this.el.taskList.innerHTML = '';
    for (const t of human.tasks) {
      const def = sim.world.taskById(t.id);
      const li = document.createElement('li');
      li.className = t.done ? 'done' : next === t ? 'next' : '';
      li.innerHTML = `<span class="mark">${t.done ? '✔' : '▸'}</span><span>${def.name} — ${
        sim.world.roomNameAt(def.x, def.y)
      }</span>`;
      this.el.taskList.appendChild(li);
    }
    this.el.taskList.classList.toggle('blocked', blocked);
  }

  updateSabotage(sim) {
    const s = sim.sabotage;
    if (!s) {
      this.el.sabotageBanner.classList.add('hidden');
      return;
    }
    this.el.sabotageBanner.classList.remove('hidden');
    const station = sim.world.fixStations.find((x) => x.fixes === s.type);
    const left = Math.max(0, Math.ceil(s.until - sim.time));
    this.el.sabotageBanner.textContent =
      s.type === 'fog'
        ? `🌫️ Туман! Видно только под носом. Рубильник: ${station.name} (${left} с)`
        : `📡 Связь глушится. Починка: ${station.name} (${left} с)`;
  }

  updateActions(sim, ctx) {
    const human = sim.human;
    const imp = sim.isImpostor(human);
    const set = (btn, ready, label) => {
      btn.classList.toggle('ready', !!ready);
      if (label && btn.dataset.label !== label) {
        btn.dataset.label = label;
        btn.innerHTML = label;
      }
    };
    if (sim.phase !== PHASE.PLAYING) {
      for (const b of [this.el.btnUse, this.el.btnReport, this.el.btnKill, this.el.btnVent, this.el.btnSabotage, this.el.btnEmergency]) {
        b.classList.remove('ready');
      }
      return;
    }

    if (ctx.fix) set(this.el.btnUse, true, `<span class="key">E</span>Починить`);
    else if (ctx.task) set(this.el.btnUse, true, `<span class="key">E</span>Выполнить`);
    else set(this.el.btnUse, false);

    set(this.el.btnReport, !!ctx.body);
    set(this.el.btnEmergency, !!(ctx.pad && ctx.pad.ready),
      ctx.pad && !ctx.pad.ready ? `<span class="key">G</span>Сбор (${Math.ceil(sim.emergencyCooldown)} с)` : null);

    if (imp && human.alive) {
      if (ctx.kill) {
        const ready = ctx.kill.ready;
        set(this.el.btnKill, ready,
          ready ? `<span class="key">Q</span>Убить ${ctx.kill.target.name}` : `<span class="key">Q</span>Клык (${Math.ceil(human.killCooldown)} с)`);
      } else {
        set(this.el.btnKill, false, human.killCooldown > 0 ? `<span class="key">Q</span>Клык (${Math.ceil(human.killCooldown)} с)` : null);
      }
      set(this.el.btnVent, !!ctx.vent, human.vented ? `<span class="key">V</span>Вылезти` : null);
      set(this.el.btnSabotage, !sim.sabotage && sim.sabotageCooldown <= 0,
        !sim.sabotage && sim.sabotageCooldown > 0 ? `<span class="key">X</span>Саботаж (${Math.ceil(sim.sabotageCooldown)} с)` : null);
    }
  }

  toast(text, kind = '', ms = 3400) {
    const div = document.createElement('div');
    div.className = `toast ${kind}`;
    div.textContent = text;
    this.el.toastWrap.appendChild(div);
    setTimeout(() => {
      div.style.transition = 'opacity 0.4s';
      div.style.opacity = '0';
      setTimeout(() => div.remove(), 420);
    }, ms);
  }

  // -------------------------------------------------------- собрание
  openMeeting(sim, payload) {
    this.show('meeting', true);
    this.el.meetingTitle.className = payload.reason === 'report' ? 'report' : '';
    this.el.meetingTitle.textContent = payload.reason === 'report' ? '🐸 ТРУП НАЙДЕН!' : '🔔 ЭКСТРЕННЫЙ СБОР';
    this.el.meetingSub.textContent =
      payload.reason === 'report'
        ? `${payload.body.name} нашли в локации «${payload.body.room}». Кто это сделал?`
        : 'Кто-то нажал на большую кувшинку. Говорите!';
    this._lastVotes = -1;
    this.buildVoteGrid(sim);
  }

  buildVoteGrid(sim) {
    const grid = this.el.voteGrid;
    grid.innerHTML = '';
    const skip = document.createElement('div');
    skip.className = 'vote-card skip';
    skip.dataset.target = 'skip';
    skip.textContent = 'Пропустить голосование';
    skip.addEventListener('click', () => this.h.onVote(null));
    grid.appendChild(skip);

    for (const p of sim.players) {
      const card = document.createElement('div');
      card.className = `vote-card${p.alive ? '' : ' dead'}`;
      card.dataset.target = p.id;
      const canvas = document.createElement('canvas');
      drawFrogAvatar(canvas, p.suit, { size: 72, dead: !p.alive });
      const nm = document.createElement('div');
      nm.className = 'nm';
      nm.textContent = p.isHuman ? `${p.name} (вы)` : p.name;
      const chips = document.createElement('div');
      chips.className = 'chips';
      card.append(canvas, nm, chips);
      if (p.alive) card.addEventListener('click', () => this.h.onVote(p.id));
      grid.appendChild(card);
    }
  }

  updateMeeting(sim) {
    const total = sim.phase === PHASE.DISCUSSION ? CONFIG.discussionTime : CONFIG.votingTime;
    const ratio = Math.max(0, Math.min(1, sim.phaseTimer / total));
    this.el.timerFill.style.width = `${ratio * 100}%`;
    this.el.timerFill.style.background =
      sim.phase === PHASE.DISCUSSION
        ? 'linear-gradient(90deg,#8fd6c0,#6fe38d)'
        : 'linear-gradient(90deg,#ffcf5c,#ff8b5c)';

    const alive = sim.alivePlayers();
    const voted = alive.filter((p) => sim.votes.has(p.id)).length;
    this.el.voteStatus.textContent =
      sim.phase === PHASE.DISCUSSION
        ? `Обсуждение. Голосование начнётся через ${Math.ceil(sim.phaseTimer)} с.`
        : `Голосуют: ${voted} из ${alive.length} · осталось ${Math.ceil(sim.phaseTimer)} с`;
    this.el.btnSkip.disabled = sim.phase !== PHASE.DISCUSSION;

    if (voted !== this._lastVotes) {
      this._lastVotes = voted;
      for (const card of this.el.voteGrid.querySelectorAll('.vote-card')) {
        const chips = card.querySelector('.chips');
        if (chips) chips.innerHTML = '';
        card.classList.remove('picked');
      }
      for (const [voterId, targetId] of sim.votes) {
        const voter = sim.playerById(voterId);
        const card = this.el.voteGrid.querySelector(`[data-target="${targetId === null ? 'skip' : targetId}"]`);
        if (!card || !voter) continue;
        const chip = document.createElement('span');
        chip.className = 'chip';
        chip.style.background = voter.suit.body;
        card.querySelector('.chips')?.appendChild(chip);
        if (voter.isHuman) card.classList.add('picked');
      }
    }
  }

  closeMeeting() {
    this.show('meeting', false);
  }

  // ---------------------------------------------------------- выброс
  showEject(sim, payload) {
    if (!payload.ejectedId) {
      this.el.ejectText.textContent = payload.text;
      this.el.ejectFrog.style.display = 'none';
    } else {
      this.el.ejectFrog.style.display = '';
      // перезапуск CSS-анимации
      this.el.ejectFrog.style.animation = 'none';
      void this.el.ejectFrog.offsetWidth;
      this.el.ejectFrog.style.animation = '';
      drawFrogAvatar(this.el.ejectFrog, payload.suit, { size: 120 });
      this.el.ejectText.textContent = payload.text;
    }
    this.show('eject', true);
  }

  hideEject() {
    this.show('eject', false);
  }

  // ----------------------------------------------------------- финал
  showEnd(sim, payload, stats) {
    const crewWin = payload.winner === 'crew';
    this.el.endTitle.textContent = crewWin ? '🏆 ПОБЕДА МИРНЫХ ЛЯГУШЕК' : '💀 САМОВАНЦЫ ЗАХВАТИЛИ ПРУД';
    this.el.endTitle.className = crewWin ? 'crew' : 'impostor';
    this.el.endReason.textContent = payload.reason;
    this.el.endImpostors.innerHTML = '';
    for (const imp of payload.impostors) {
      const card = document.createElement('div');
      card.className = 'imp-card';
      const c = document.createElement('canvas');
      drawFrogAvatar(c, imp.suit, { size: 76 });
      const nm = document.createElement('div');
      nm.textContent = imp.name === sim.human.name ? `${imp.name} (вы)` : imp.name;
      card.append(c, nm);
      this.el.endImpostors.appendChild(card);
    }
    this.el.endStats.innerHTML = stats;
    this.show('end', true);
    this.show('hud', false);
  }

  // ----------------------------------------------------------- пауза
  showPause(sim, on) {
    this.show('pause', on);
    if (on && sim) {
      this.el.pauseInfo.innerHTML =
        `Роль: <b>${sim.isImpostor(sim.human) ? 'самозванец' : 'мирная лягушка'}</b><br>` +
        `Живых: <b>${sim.alivePlayers().length}</b> из ${sim.players.length}<br>` +
        `Заданий пруда: <b>${sim.crewTaskProgress().done}/${sim.crewTaskProgress().total}</b>`;
    }
  }
}

export default UI;
