// Renderer — отрисовка мира на canvas (вид сбоку, «пиксельный» стиль).
import { T, BLOCK_COLORS } from './world.js';

const CELL = 24; // логический размер клетки

export class Renderer {
  constructor(canvas) {
    this.canvas = canvas;
    this.ctx = canvas.getContext('2d');
    this.time = 0;
    this.bulbs = [];      // вспышки при добыче: {x, y, t0}
    this.marks = new Set(); // где были срублены блоки
  }

  sizeTo(world) {
    const dpr = Math.min(2, window.devicePixelRatio || 1);
    this.canvas.width = Math.round(world.w * CELL * dpr);
    this.canvas.height = Math.round(world.h * CELL * dpr);
    this.ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  }

  markMined(x, y) { this.marks.add(x + ',' + y); this.bulbs.push({ x, y, t0: this.time }); }
  clearMarks() { this.marks.clear(); this.bulbs.length = 0; }

  draw(world, night, showTarget) {
    const ctx = this.ctx;
    const Wpx = world.w * CELL;
    const Hpx = world.h * CELL;

    // небо
    if (!night) {
      const g = ctx.createLinearGradient(0, 0, 0, Hpx);
      g.addColorStop(0, '#7ec8f7');
      g.addColorStop(1, '#c9eafc');
      ctx.fillStyle = g;
    } else {
      const g = ctx.createLinearGradient(0, 0, 0, Hpx);
      g.addColorStop(0, '#0b0f2a');
      g.addColorStop(1, '#1a1030');
      ctx.fillStyle = g;
    }
    ctx.fillRect(0, 0, Wpx, Hpx);

    if (!night) {
      ctx.fillStyle = 'rgba(255,255,255,0.5)';
      for (let i = 0; i < 3; i++) {
        const cw = (this.time * 4 + i * 260) % (Wpx + 160) - 80;
        this.cloud(ctx, cw + 40, 24 + i * 26);
      }
      // солнце
      ctx.fillStyle = '#ffd75e';
      ctx.beginPath(); ctx.arc(Wpx - 50, 34, 13, 0, Math.PI * 2); ctx.fill();
    } else {
      // луна и звёзды
      ctx.fillStyle = '#e8eaf6';
      ctx.beginPath(); ctx.arc(Wpx - 50, 34, 11, 0, Math.PI * 2); ctx.fill();
      ctx.fillStyle = '#0b0f2a';
      ctx.beginPath(); ctx.arc(Wpx - 46, 31, 9, 0, Math.PI * 2); ctx.fill();
      ctx.fillStyle = 'rgba(255,255,255,0.8)';
      for (let i = 0; i < 30; i++) {
        ctx.fillRect((i * 137.3) % Wpx, (i * 53.7) % (world.walkY * CELL - 12), 2, 2);
      }
    }

    // блоки
    for (let y = 0; y < world.h; y++) {
      for (let x = 0; x < world.w; x++) {
        const t = world.grid[world.idx(x, y)];
        if (t === T.AIR) continue;
        const px = x * CELL, py = y * CELL;
        ctx.fillStyle = BLOCK_COLORS[t];
        ctx.fillRect(px, py, CELL, CELL);

        ctx.fillStyle = 'rgba(255,255,255,0.10)';
        ctx.fillRect(px, py, CELL, 3);
        ctx.fillStyle = 'rgba(0,0,0,0.18)';
        ctx.fillRect(px, py + CELL - 3, CELL, 3);

        if (t === T.LEAF) {
          ctx.fillStyle = 'rgba(255,255,255,0.12)';
          ctx.fillRect(px + 4, py + 4, 6, 6);
        }
        if (t === T.COAL) {
          ctx.fillStyle = '#6f6f80';
          ctx.fillRect(px + 6, py + 6, 6, 6);
          ctx.fillStyle = '#a8a8bc';
          ctx.fillRect(px + 6, py + 6, 2, 2);
        }
        if (t === T.GRASS) {
          ctx.fillStyle = '#7cc25a';
          ctx.fillRect(px, py, CELL, 5);
        }
        if (night) {
          ctx.fillStyle = 'rgba(8,10,40,0.4)';
          ctx.fillRect(px, py, CELL, CELL);
        }
      }
    }

    // отметки о добытом
    ctx.fillStyle = 'rgba(0,0,0,0.30)';
    for (const k of this.marks) {
      const [x, y] = k.split(',').map(Number);
      ctx.fillRect(x * CELL + 3, y * CELL + 3, CELL - 6, CELL - 6);
    }

    // цель
    if (showTarget) {
      const n = world.nearest();
      if (n) {
        const pulse = 0.5 + 0.5 * Math.sin(this.time * 5);
        ctx.strokeStyle = `rgba(255,240,120,${0.45 + 0.4 * pulse})`;
        ctx.lineWidth = 2;
        ctx.strokeRect(n.x * CELL + 1, n.y * CELL + 1, CELL + 2, CELL + 2);
      }
    }

    // вспышки
    this.bulbs = this.bulbs.filter((b) => {
      const age = this.time - b.t0;
      if (age >= 0.45) return false;
      const r = age * 130;
      ctx.strokeStyle = `rgba(255,255,255,${1 - age / 0.45})`;
      ctx.lineWidth = 2;
      ctx.beginPath();
      ctx.arc(b.x * CELL + CELL / 2, b.y * CELL + CELL / 2, r, 0, Math.PI * 2);
      ctx.stroke();
      return true;
    });

    this.drawAgent(ctx, world.agent, night);

    ctx.font = 'bold 11px monospace';
    ctx.fillStyle = night ? 'rgba(255,255,255,0.85)' : 'rgba(20,24,60,0.8)';
    ctx.fillText(`⛏ ${world.collected}/${world.total}`, 6, 13);
  }

  cloud(ctx, cx, cy) {
    ctx.beginPath();
    ctx.arc(cx, cy, 8, 0, Math.PI * 2);
    ctx.arc(cx + 12, cy - 4, 10, 0, Math.PI * 2);
    ctx.arc(cx + 24, cy, 7, 0, Math.PI * 2);
    ctx.fill();
  }

  drawAgent(ctx, agent, night) {
    const px = agent.x * CELL, py = agent.y * CELL;
    const dirFlip = agent.dir === -1;

    ctx.save();
    ctx.translate(px + CELL / 2, py + CELL / 2);
    if (dirFlip) ctx.scale(-1, 1);
    ctx.translate(-CELL / 2, -CELL / 2);

    // тело (куртка Стива)
    ctx.fillStyle = night ? '#20304f' : '#18a9b8';
    ctx.fillRect(5, 10, 14, 12);
    ctx.fillStyle = night ? '#7a3b4f' : '#3b7a5a';
    ctx.fillRect(5, 16, 14, 6);
    // голова
    ctx.fillStyle = night ? '#5a3a24' : '#c88a52';
    ctx.fillRect(6, 1, 12, 10);
    // лицо
    ctx.fillStyle = '#fff';
    ctx.fillRect(9, 5, 2, 2);
    ctx.fillRect(14, 5, 2, 2);
    ctx.fillStyle = '#3a2a1a';
    ctx.fillRect(9, 8, 7, 2);

    ctx.restore();

    if (night) {
      ctx.font = '12px sans-serif';
      ctx.fillText('💤', px + 14, py - 3);
    }
  }
}
