// Отрисовка мира пруда, лягушек, тумана войны и миникарты.
import { CONFIG } from '../core/config.js';
import { drawFrog } from './frog.js';
import { makeRng } from '../core/rng.js';

const WALL = '#0c1f16';
const CORRIDOR_FLOOR = '#2b3a31';

function lilyPad(ctx, x, y, r, rot = 0) {
  ctx.save();
  ctx.translate(x, y);
  ctx.rotate(rot);
  ctx.beginPath();
  ctx.moveTo(0, 0);
  ctx.arc(0, 0, r, 0.35, Math.PI * 2 - 0.35);
  ctx.closePath();
  ctx.fillStyle = '#3f8a4a';
  ctx.fill();
  ctx.strokeStyle = 'rgba(20,50,25,0.5)';
  ctx.lineWidth = 1.2;
  ctx.stroke();
  ctx.beginPath();
  ctx.moveTo(0, 0);
  ctx.lineTo(-r * 0.8, -r * 0.4);
  ctx.moveTo(0, 0);
  ctx.lineTo(-r * 0.2, -r * 0.9);
  ctx.strokeStyle = 'rgba(255,255,255,0.12)';
  ctx.stroke();
  ctx.restore();
}

export class Renderer {
  constructor(canvas, world) {
    this.canvas = canvas;
    this.ctx = canvas.getContext('2d');
    this.world = world;
    this.scale = 1;
    this.cam = { x: 0, y: 0 };
    this.t = 0;
    this.shake = 0;
    this.decor = this._makeDecor();
    this.flies = this._makeFlies();
    this.speckles = this._makeSpeckles();
    this.resize();
  }

  resize() {
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    const w = this.canvas.clientWidth || window.innerWidth;
    const h = this.canvas.clientHeight || window.innerHeight;
    this.canvas.width = Math.floor(w * dpr);
    this.canvas.height = Math.floor(h * dpr);
    this.viewW = w;
    this.viewH = h;
    this.dpr = dpr;
    this.scale = Math.max(0.7, Math.min(1.6, Math.max(w / 1050, h / 680)));
  }

  _makeDecor() {
    const rng = makeRng(20240607);
    const list = [];
    for (const room of this.world.rooms) {
      const area = { x: room.x + 12, y: room.y + 12, w: room.w - 24, h: room.h - 24 };
      const push = (type, x, y, extra = {}) => list.push({ type, x, y, room: room.id, ...extra });
      const n = Math.floor((room.w * room.h) / 26000) + 4;
      for (let i = 0; i < n; i++) {
        const x = rng.range(area.x, area.x + area.w);
        const y = rng.range(area.y, area.y + area.h);
        switch (room.kind) {
          case 'water':
            push(rng.chance(0.6) ? 'lily' : 'ripple', x, y, { r: rng.range(12, 26), rot: rng.range(0, 6.28) });
            break;
          case 'reeds':
            push('reed', x, y, { h: rng.range(26, 48), lean: rng.range(-0.2, 0.2) });
            break;
          case 'grass':
            push(rng.chance(0.55) ? 'lily' : 'flower', x, y, { r: rng.range(8, 16), hue: rng.range(0, 360) });
            break;
          case 'glass':
            push(rng.chance(0.5) ? 'pot' : 'grid', x, y, { w: rng.range(60, 110) });
            break;
          case 'wood':
            push('plank', x, y, { w: room.w });
            break;
          case 'tile':
            push('tile', x, y);
            break;
          case 'metal':
            push(rng.chance(0.4) ? 'pipe' : 'rivet', x, y, { w: rng.range(50, 110) });
            break;
          case 'dirt':
            push('clod', x, y, { r: rng.range(4, 11) });
            break;
          case 'mud':
            push(rng.chance(0.6) ? 'bubble' : 'reed', x, y, {
              r: rng.range(4, 12),
              h: rng.range(20, 38),
              sp: rng.range(0.4, 1.3),
              ph0: rng.range(0, 3),
            });
            break;
          default:
            push('clod', x, y, { r: rng.range(4, 10) });
        }
      }
    }
    return list;
  }

  _makeFlies() {
    const rng = makeRng(99);
    return Array.from({ length: 34 }, () => ({
      x: rng.range(100, this.world.width - 100),
      y: rng.range(100, this.world.height - 100),
      r: rng.range(0, 6.28),
      sp: rng.range(0.6, 1.8),
    }));
  }

  // ------------------------------------------------------------- камера
  follow(target) {
    const halfW = this.viewW / (2 * this.scale);
    const halfH = this.viewH / (2 * this.scale);
    const maxX = Math.max(0, this.world.width - halfW * 2);
    const maxY = Math.max(0, this.world.height - halfH * 2);
    this.cam.x = Math.max(0, Math.min(maxX, target.x - halfW));
    this.cam.y = Math.max(0, Math.min(maxY, target.y - halfH));
  }

  screenToWorld(sx, sy) {
    return { x: sx / this.scale + this.cam.x, y: sy / this.scale + this.cam.y };
  }

  worldToScreen(wx, wy) {
    return { x: (wx - this.cam.x) * this.scale, y: (wy - this.cam.y) * this.scale };
  }

  kick(amount = 8) {
    this.shake = Math.max(this.shake, amount);
  }

  // --------------------------------------------------------------- кадр
  draw(sim, dt, follow) {
    this.t += dt;
    const ctx = this.ctx;
    const human = follow || sim.human;
    this.follow(human);

    let ox = 0;
    let oy = 0;
    if (this.shake > 0.2) {
      ox = (Math.random() - 0.5) * this.shake;
      oy = (Math.random() - 0.5) * this.shake;
      this.shake *= 0.86;
    } else {
      this.shake = 0;
    }

    ctx.setTransform(this.dpr, 0, 0, this.dpr, 0, 0);
    ctx.fillStyle = '#07130d';
    ctx.fillRect(0, 0, this.viewW, this.viewH);

    ctx.save();
    ctx.translate(ox, oy);
    ctx.scale(this.scale, this.scale);
    ctx.translate(-this.cam.x, -this.cam.y);

    this._drawGround(ctx);
    this._drawWalls(ctx);
    this._drawFloors(ctx);
    this._drawDecor(ctx);
    this._drawLabels(ctx);
    this._drawVents(ctx, sim);
    this._drawStations(ctx, sim);
    this._drawPad(ctx, sim);
    this._drawFixStations(ctx, sim);
    this._drawFlies(ctx);
    this._drawBodies(ctx, sim, human);
    this._drawPlayers(ctx, sim, human);
    ctx.restore();

    this._drawFog(ctx, sim, human);
    this._drawSabotageFx(ctx, sim);
    this._drawTaskArrow(ctx, sim, human);
    this._drawMinimap(ctx, sim, human);
    this._drawRoomLabel(ctx, sim, human);
  }

  _makeSpeckles() {
    const rng = makeRng(5);
    return Array.from({ length: 900 }, () => ({
      x: rng.range(0, this.world.width),
      y: rng.range(0, this.world.height),
    }));
  }

  _drawGround(ctx) {
    ctx.fillStyle = '#12301f';
    ctx.fillRect(0, 0, this.world.width, this.world.height);
    ctx.fillStyle = 'rgba(255,255,255,0.03)';
    for (const s of this.speckles) ctx.fillRect(s.x, s.y, 2, 2);
  }

  _drawWalls(ctx) {
    ctx.fillStyle = WALL;
    for (const a of this.world.areas) {
      ctx.fillRect(a.x - 8, a.y - 8, a.w + 16, a.h + 16);
    }
  }

  _drawFloors(ctx) {
    for (const c of this.world.corridors) {
      ctx.fillStyle = CORRIDOR_FLOOR;
      ctx.fillRect(c.x, c.y, c.w, c.h);
    }
    for (const r of this.world.rooms) {
      ctx.fillStyle = r.floor;
      ctx.fillRect(r.x, r.y, r.w, r.h);
      ctx.strokeStyle = 'rgba(0,0,0,0.25)';
      ctx.lineWidth = 3;
      ctx.strokeRect(r.x + 1.5, r.y + 1.5, r.w - 3, r.h - 3);
    }
  }

  _drawDecor(ctx) {
    for (const d of this.decor) {
      switch (d.type) {
        case 'lily':
          lilyPad(ctx, d.x, d.y, d.r, d.rot);
          break;
        case 'ripple':
          ctx.strokeStyle = 'rgba(255,255,255,0.08)';
          ctx.lineWidth = 1.4;
          ctx.beginPath();
          ctx.ellipse(d.x, d.y, d.r, d.r * 0.45, 0, 0, Math.PI * 2);
          ctx.stroke();
          break;
        case 'reed': {
          ctx.strokeStyle = '#4f7a3a';
          ctx.lineWidth = 3;
          ctx.beginPath();
          ctx.moveTo(d.x, d.y);
          ctx.quadraticCurveTo(d.x + (d.lean || 0) * 20, d.y - d.h * 0.6, d.x + (d.lean || 0) * 34, d.y - d.h);
          ctx.stroke();
          ctx.fillStyle = '#6b4a2a';
          ctx.beginPath();
          ctx.ellipse(d.x + (d.lean || 0) * 34, d.y - d.h - 5, 3, 7, 0, 0, Math.PI * 2);
          ctx.fill();
          break;
        }
        case 'flower':
          ctx.fillStyle = `hsla(${d.hue},70%,70%,0.6)`;
          ctx.beginPath();
          ctx.arc(d.x, d.y, 3.4, 0, Math.PI * 2);
          ctx.fill();
          break;
        case 'grid':
          ctx.strokeStyle = 'rgba(255,255,255,0.06)';
          ctx.lineWidth = 1;
          ctx.strokeRect(d.x, d.y, d.w, d.w * 0.6);
          break;
        case 'pot':
          ctx.fillStyle = '#7b5233';
          ctx.fillRect(d.x, d.y, 22, 18);
          ctx.fillStyle = '#3f8a4a';
          ctx.beginPath();
          ctx.arc(d.x + 11, d.y - 4, 12, Math.PI, 0);
          ctx.fill();
          break;
        case 'plank':
          ctx.strokeStyle = 'rgba(0,0,0,0.2)';
          ctx.lineWidth = 2;
          ctx.beginPath();
          ctx.moveTo(d.x, d.y);
          ctx.lineTo(d.x + 120, d.y);
          ctx.stroke();
          break;
        case 'tile':
          ctx.strokeStyle = 'rgba(255,255,255,0.05)';
          ctx.lineWidth = 1;
          ctx.strokeRect(d.x, d.y, 50, 50);
          break;
        case 'pipe':
          ctx.fillStyle = 'rgba(180,180,170,0.18)';
          ctx.fillRect(d.x, d.y, d.w, 12);
          break;
        case 'rivet':
          ctx.fillStyle = 'rgba(255,255,255,0.1)';
          ctx.beginPath();
          ctx.arc(d.x, d.y, 2.6, 0, Math.PI * 2);
          ctx.fill();
          break;
        case 'clod':
          ctx.fillStyle = 'rgba(0,0,0,0.22)';
          ctx.beginPath();
          ctx.ellipse(d.x, d.y, d.r, d.r * 0.7, 0, 0, Math.PI * 2);
          ctx.fill();
          break;
        case 'bubble': {
          const ph = (this.t * d.sp + d.ph0) % 3;
          ctx.strokeStyle = `rgba(190,240,200,${0.25 - ph * 0.06})`;
          ctx.lineWidth = 1.2;
          ctx.beginPath();
          ctx.arc(d.x, d.y - ph * 6, d.r, 0, Math.PI * 2);
          ctx.stroke();
          break;
        }
        default:
          break;
      }
    }
  }

  _drawLabels(ctx) {
    ctx.font = '600 19px system-ui, sans-serif';
    ctx.textAlign = 'center';
    for (const r of this.world.rooms) {
      ctx.fillStyle = 'rgba(255,255,255,0.14)';
      ctx.fillText(r.name.toUpperCase(), r.x + r.w / 2, r.y + 34);
    }
    ctx.textAlign = 'left';
  }

  _drawVents(ctx, sim) {
    const isImp = sim.isImpostor(sim.human);
    for (const v of this.world.vents) {
      ctx.fillStyle = '#0a1a12';
      ctx.beginPath();
      ctx.ellipse(v.x, v.y, 20, 13, 0, 0, Math.PI * 2);
      ctx.fill();
      ctx.strokeStyle = isImp ? 'rgba(120,255,170,0.55)' : 'rgba(120,160,130,0.35)';
      ctx.lineWidth = 2.4;
      ctx.stroke();
      ctx.fillStyle = 'rgba(0,0,0,0.55)';
      ctx.beginPath();
      ctx.ellipse(v.x, v.y + 1, 13, 8, 0, 0, Math.PI * 2);
      ctx.fill();
    }
  }

  _drawStations(ctx, sim) {
    const human = sim.human;
    const mine = new Set(human.tasks.map((t) => t.id));
    for (const t of this.world.tasks) {
      const task = human.tasks.find((x) => x.id === t.id);
      const done = task ? task.done : false;
      const highlight = mine.has(t.id) && !done;
      ctx.save();
      ctx.translate(t.x, t.y);
      ctx.fillStyle = highlight ? 'rgba(255,230,120,0.16)' : 'rgba(255,255,255,0.07)';
      ctx.beginPath();
      ctx.arc(0, 0, 22, 0, Math.PI * 2);
      ctx.fill();
      ctx.strokeStyle = highlight ? '#ffd76a' : 'rgba(255,255,255,0.3)';
      ctx.lineWidth = 2;
      ctx.stroke();
      if (task && !done && task.progress > 0) {
        ctx.strokeStyle = '#7dff9e';
        ctx.lineWidth = 4;
        ctx.beginPath();
        ctx.arc(0, 0, 22, -Math.PI / 2, -Math.PI / 2 + (task.progress / CONFIG.taskHoldTime) * Math.PI * 2);
        ctx.stroke();
      }
      ctx.fillStyle = done ? '#7dff9e' : highlight ? '#ffd76a' : 'rgba(255,255,255,0.5)';
      ctx.font = '700 18px system-ui, sans-serif';
      ctx.textAlign = 'center';
      ctx.fillText(done ? '✔' : '!', 0, 6);
      ctx.restore();
    }
    ctx.textAlign = 'left';
  }

  _drawPad(ctx, sim) {
    const pad = this.world.emergencyPad;
    lilyPad(ctx, pad.x, pad.y, 44, 0.4);
    const ready = sim.emergencyCooldown <= 0;
    const pulse = ready ? 1 + Math.sin(this.t * 4) * 0.06 : 1;
    ctx.fillStyle = ready ? '#e74c3c' : '#7a5a55';
    ctx.beginPath();
    ctx.arc(pad.x, pad.y - 4, 15 * pulse, 0, Math.PI * 2);
    ctx.fill();
    ctx.strokeStyle = 'rgba(0,0,0,0.4)';
    ctx.lineWidth = 3;
    ctx.stroke();
    if (!ready) {
      ctx.fillStyle = 'rgba(255,255,255,0.7)';
      ctx.font = '700 12px system-ui, sans-serif';
      ctx.textAlign = 'center';
      ctx.fillText(String(Math.ceil(sim.emergencyCooldown)), pad.x, pad.y);
      ctx.textAlign = 'left';
    }
  }

  _drawFixStations(ctx, sim) {
    for (const st of this.world.fixStations) {
      const active = sim.sabotage && sim.sabotage.type === st.fixes;
      ctx.strokeStyle = active ? '#ff6b5b' : 'rgba(200,220,210,0.5)';
      ctx.lineWidth = 4;
      ctx.beginPath();
      ctx.moveTo(st.x, st.y + 14);
      ctx.lineTo(st.x, st.y - 16);
      ctx.stroke();
      ctx.beginPath();
      ctx.arc(st.x, st.y - 20, 7, 0, Math.PI * 2);
      ctx.fillStyle = active ? (Math.sin(this.t * 8) > 0 ? '#ff3b2b' : '#7a1f16') : '#8fd6c0';
      ctx.fill();
      ctx.strokeStyle = 'rgba(0,0,0,0.35)';
      ctx.lineWidth = 2;
      ctx.stroke();
    }
  }

  _drawFlies(ctx) {
    for (const f of this.flies) {
      f.r += 0.02 * f.sp;
      const x = f.x + Math.cos(f.r) * 26;
      const y = f.y + Math.sin(f.r * 1.3) * 18;
      ctx.fillStyle = 'rgba(30,30,30,0.85)';
      ctx.beginPath();
      ctx.arc(x, y, 2, 0, Math.PI * 2);
      ctx.fill();
      ctx.strokeStyle = 'rgba(255,255,255,0.35)';
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.moveTo(x - 3, y - 1.5);
      ctx.lineTo(x + 3, y - 1.5);
      ctx.stroke();
    }
  }

  _visible(sim, observer, target) {
    if (observer === target) return true;
    if (!observer.alive) return true;
    if (!target.alive) return false;
    if (target.vented && !sim.isImpostor(observer)) return false;
    const d = Math.hypot(observer.x - target.x, observer.y - target.y);
    return d <= sim.visionRadius(observer) * 1.25;
  }

  _drawBodies(ctx, sim, human) {
    for (const b of sim.bodies) {
      if (b.reported) continue;
      if (!this._visible(sim, human, { x: b.x, y: b.y, alive: true, vented: false })) continue;
      drawFrog(ctx, {
        x: b.x,
        y: b.y,
        suit: b.suit,
        dead: true,
        t: this.t,
        scale: 0.95,
      });
    }
  }

  _drawPlayers(ctx, sim, human) {
    const list = sim.players
      .filter((p) => this._visible(sim, human, p))
      .filter((p) => p.alive || p.isHuman)
      .sort((a, b) => a.y - b.y);
    for (const p of list) {
      if (p.vented && !sim.isImpostor(human)) continue;
      drawFrog(ctx, {
        x: p.x,
        y: p.y,
        suit: p.suit,
        dir: p.dir,
        walk: p.walk,
        t: this.t,
        ghost: !p.alive,
        scale: 1,
      });
      // имя
      ctx.font = '600 13px system-ui, sans-serif';
      ctx.textAlign = 'center';
      const label = p.isHuman ? `${p.name} (вы)` : p.name;
      ctx.lineWidth = 3;
      ctx.strokeStyle = 'rgba(0,0,0,0.65)';
      ctx.strokeText(label, p.x, p.y - 32);
      ctx.fillStyle = p.isHuman ? '#ffe27a' : 'rgba(255,255,255,0.85)';
      ctx.fillText(label, p.x, p.y - 32);
      ctx.textAlign = 'left';
    }
  }

  _drawFog(ctx, sim, human) {
    if (!human.alive) return; // призраки видят всё
    const center = this.worldToScreen(human.x, human.y);
    const r = sim.visionRadius(human) * this.scale;
    const g = ctx.createRadialGradient(center.x, center.y, r * 0.3, center.x, center.y, r);
    g.addColorStop(0, 'rgba(3,12,8,0)');
    g.addColorStop(0.65, 'rgba(3,12,8,0.45)');
    g.addColorStop(1, 'rgba(3,12,8,0.96)');
    ctx.fillStyle = g;
    ctx.fillRect(0, 0, this.viewW, this.viewH);
  }

  _drawSabotageFx(ctx, sim) {
    if (!sim.sabotage) return;
    if (sim.sabotage.type === 'fog') {
      ctx.fillStyle = `rgba(120,20,10,${0.1 + Math.sin(this.t * 3) * 0.03})`;
      ctx.fillRect(0, 0, this.viewW, this.viewH);
    } else {
      ctx.globalAlpha = 0.08;
      for (let y = 0; y < this.viewH; y += 4) {
        if ((y + Math.floor(this.t * 20)) % 8 === 0) {
          ctx.fillStyle = '#ffffff';
          ctx.fillRect(0, y, this.viewW, 1);
        }
      }
      ctx.globalAlpha = 1;
    }
  }

  _drawTaskArrow(ctx, sim, human) {
    if (!human.alive || sim.phase !== 'playing') return;
    const next = human.tasks.find((t) => !t.done);
    if (!next) return;
    const def = this.world.taskById(next.id);
    const s = this.worldToScreen(def.x, def.y);
    const pad = 46;
    const inside = s.x > pad && s.x < this.viewW - pad && s.y > pad && s.y < this.viewH - pad;
    if (inside) return;
    const cx = this.viewW / 2;
    const cy = this.viewH / 2;
    const a = Math.atan2(s.y - cy, s.x - cx);
    const rx = Math.min(cx - pad, Math.abs(Math.cos(a)) > 0.001 ? Math.abs((cx - pad) / Math.cos(a)) : Infinity);
    const ry = Math.min(cy - pad, Math.abs(Math.sin(a)) > 0.001 ? Math.abs((cy - pad) / Math.sin(a)) : Infinity);
    const rr = Math.min(rx, ry);
    const ax = cx + Math.cos(a) * rr;
    const ay = cy + Math.sin(a) * rr;
    ctx.save();
    ctx.translate(ax, ay);
    ctx.rotate(a);
    ctx.fillStyle = 'rgba(255,215,106,0.9)';
    ctx.beginPath();
    ctx.moveTo(14, 0);
    ctx.lineTo(-8, -9);
    ctx.lineTo(-8, 9);
    ctx.closePath();
    ctx.fill();
    ctx.restore();
  }

  _drawMinimap(ctx, sim, human) {
    const s = 0.075;
    const w = this.world.width * s;
    const h = this.world.height * s;
    const x0 = this.viewW - w - 14;
    const y0 = 14;
    ctx.save();
    ctx.globalAlpha = 0.85;
    ctx.fillStyle = 'rgba(5,18,12,0.8)';
    ctx.fillRect(x0 - 4, y0 - 4, w + 8, h + 8);
    ctx.strokeStyle = 'rgba(255,255,255,0.25)';
    ctx.lineWidth = 1;
    ctx.strokeRect(x0 - 4, y0 - 4, w + 8, h + 8);
    for (const a of this.world.areas) {
      const room = this.world.rooms.includes(a);
      ctx.fillStyle = room ? 'rgba(90,160,110,0.55)' : 'rgba(90,160,110,0.3)';
      ctx.fillRect(x0 + a.x * s, y0 + a.y * s, a.w * s, a.h * s);
    }
    if (sim.isImpostor(human)) {
      ctx.fillStyle = 'rgba(255,90,70,0.9)';
      for (const v of this.world.vents) ctx.fillRect(x0 + v.x * s - 1.5, y0 + v.y * s - 1.5, 3, 3);
    }
    for (const t of human.tasks) {
      if (t.done) continue;
      const def = this.world.taskById(t.id);
      ctx.fillStyle = 'rgba(255,220,110,0.9)';
      ctx.fillRect(x0 + def.x * s - 1.5, y0 + def.y * s - 1.5, 3, 3);
    }
    ctx.fillStyle = '#ffe27a';
    ctx.beginPath();
    ctx.arc(x0 + human.x * s, y0 + human.y * s, 3.2, 0, Math.PI * 2);
    ctx.fill();
    ctx.restore();
  }

  _drawRoomLabel(ctx, sim, human) {
    ctx.font = '600 13px system-ui, sans-serif';
    ctx.fillStyle = 'rgba(255,255,255,0.5)';
    ctx.fillText(this.world.roomNameAt(human.x, human.y), 16, this.viewH - 16);
  }
}

export default Renderer;
