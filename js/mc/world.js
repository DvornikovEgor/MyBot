// World — сеточный майнкрафт-подобный мир (вид сбоку).
// Плоская «лужайка» с деревьями и углём. Агент ходит влево/вправо
// по траве и добывает блок перед собой. Мир детерминирован сидом
// и воспроизводится по ссылке (?seed=…).

export const T = { AIR: 0, GRASS: 1, STONE: 2, WOOD: 3, LEAF: 4, COAL: 5 };

export const BLOCK_COLORS = {
  [T.AIR]: null,
  [T.GRASS]: '#5c8f46',
  [T.STONE]: '#8a8f9a',
  [T.WOOD]: '#8a5a2b',
  [T.LEAF]: '#3f7d2f',
  [T.COAL]: '#3a3a40',
};

// Награда за добычу блока.
export const BLOCK_REWARD = { [T.WOOD]: 10, [T.COAL]: 15, [T.STONE]: 6 };

// «Компас» — награда за шаг в сторону ближайшего блока (reward shaping).
// Помогает агенту увидеть сигнал сквозь длинную цепочку действий.
export const SHAPE = 1;

export const BLOCK_NAME = { [T.WOOD]: 'дерево', [T.COAL]: 'уголь', [T.STONE]: 'камень' };

export function hashString(str) {
  let h = 2166136261 >>> 0;
  for (let i = 0; i < str.length; i++) {
    h ^= str.charCodeAt(i);
    h = Math.imul(h, 16777619);
  }
  return h >>> 0;
}

// Детерминированный PRNG (mulberry32).
export function mulberry32(seed) {
  let a = seed >>> 0;
  return function () {
    a |= 0; a = (a + 0x6D2B79F5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

export class World {
  constructor(width, height, seed) {
    this.w = width;
    this.h = height;
    this.groundY = height - 3;     // ряд травы
    this.walkY = this.groundY - 1; // ряд, по которому ходит агент
    this.seed = seed;
    this.maxSteps = 600;           // таймаут эпизода
    this.grid = new Uint8Array(width * height);
    this.reset();
  }

  idx(x, y) { return y * this.w + x; }
  inBounds(x, y) { return x >= 0 && x < this.w && y >= 0 && y < this.h; }
  get(x, y) { return this.inBounds(x, y) ? this.grid[this.idx(x, y)] : null; }
  set(x, y, t) { if (this.inBounds(x, y)) this.grid[this.idx(x, y)] = t; }

  reset() {
    const rnd = mulberry32(this.seed);
    this.grid.fill(T.AIR);
    this.mineables = [];   // оставшиеся блоки для добычи: {x, y, kind}
    this.collected = 0;
    this.epSteps = 0;
    this.epReward = 0;

    // Земля: ряд травы + слои камня ниже.
    for (let x = 0; x < this.w; x++) {
      this.set(x, this.groundY, T.GRASS);
      this.set(x, this.groundY + 1, T.STONE);
      this.set(x, this.groundY + 2, T.STONE);
    }

    // Деревья: столбик ствола + крона (добываются за один удар, крона осыпается).
    const treeCols = [];
    for (let i = 0; i < 600 && treeCols.length < 12; i++) {
      const x = 3 + ((rnd() * (this.w - 6)) | 0);
      if (treeCols.some((c) => Math.abs(c - x) < 4)) continue;
      treeCols.push(x);
    }
    for (const x of treeCols) {
      this.set(x, this.walkY, T.WOOD);
      this.set(x, this.walkY - 1, T.LEAF);
      this.set(x - 1, this.walkY - 1, T.LEAF);
      this.set(x + 1, this.walkY - 1, T.LEAF);
      this.set(x, this.walkY - 2, T.LEAF);
      this.mineables.push({ x, y: this.walkY, kind: T.WOOD });
    }

    // Уголь — точечно на лужайке, не вплотную к деревьям.
    const coalCols = [];
    for (let i = 0; i < 600 && coalCols.length < 10; i++) {
      const x = 3 + ((rnd() * (this.w - 6)) | 0);
      if (treeCols.some((c) => Math.abs(c - x) < 3)) continue;
      if (coalCols.some((c) => Math.abs(c - x) < 3)) continue;
      coalCols.push(x);
    }
    for (const x of coalCols) {
      this.set(x, this.walkY, T.COAL);
      this.mineables.push({ x, y: this.walkY, kind: T.COAL });
    }
    this.mineables.sort((a, b) => a.x - b.x);
    this.total = this.mineables.length;

    // Агент — в центре лужайки, на свободной клетке (блоки есть с обеих сторон).
    let sx = (this.w / 2) | 0;
    for (let d = 0; d < this.w; d++) {
      if (this.get(sx + d, this.walkY) === T.AIR) { sx = sx + d; break; }
      if (this.get(sx - d, this.walkY) === T.AIR) { sx = sx - d; break; }
    }
    this.agent = { x: sx, y: this.walkY, dir: 1 };
  }

  // === Действия ===
  move(dx) {
    const nx = this.agent.x + dx;
    this.agent.dir = dx;
    if (nx < 0 || nx >= this.w) return false;                       // край мира
    if (this.grid[this.idx(nx, this.walkY)] !== T.AIR) return false; // впереди блок
    this.agent.x = nx;
    return true;
  }

  // Добыть блок перед агентом. Возвращает {kind, reward} или null.
  mine() {
    const fx = this.agent.x + this.agent.dir;
    const t = this.get(fx, this.walkY);
    if (t !== T.WOOD && t !== T.COAL) return null;

    this.set(fx, this.walkY, T.AIR);
    if (t === T.WOOD) { // крона осыпается вместе со стволом
      this.set(fx, this.walkY - 1, T.AIR);
      this.set(fx - 1, this.walkY - 1, T.AIR);
      this.set(fx + 1, this.walkY - 1, T.AIR);
      this.set(fx, this.walkY - 2, T.AIR);
    }
    const i = this.mineables.findIndex((m) => m.x === fx && m.y === this.walkY);
    if (i >= 0) this.mineables.splice(i, 1);
    this.collected++;
    return { x: fx, kind: t, reward: BLOCK_REWARD[t], remain: this.mineables.length };
  }

  remaining() { return this.mineables.length; }

  // Ближайший оставшийся блок (цель навигации).
  nearest() {
    let best = null, bd = Infinity;
    for (const m of this.mineables) {
      const d = Math.abs(m.x - this.agent.x);
      if (d < bd) { bd = d; best = m; }
    }
    return best;
  }

  blockAhead() {
    const t = this.get(this.agent.x + this.agent.dir, this.walkY);
    return t === T.WOOD || t === T.COAL;
  }

  // Признаки состояния для Q-learning.
  getState() {
    const n = this.nearest();
    let dx = 0;
    if (n) dx = Math.max(-3, Math.min(3, n.x - this.agent.x));
    return { sdx: dx, inFront: this.blockAhead() ? 1 : 0 };
  }

  // Выполнить действие 0..3, вернуть {reward, done, success}.
  // 0 — влево, 1 — вправо, 2 — добыть, 3 — стоять.
  // В награду добавляется «компас»: +1 за приближение к ближайшему блоку, −1 за удаление.
  step(action) {
    this.epSteps++;
    let reward = 0;
    const dBefore = this.nearest() ? Math.abs(this.nearest().x - this.agent.x) : 0;

    switch (action) {
      case 0: this.move(-1); break;
      case 1: this.move(1); break;
      case 2:
        if (this.blockAhead()) {
          const res = this.mine();
          reward = res ? res.reward : 0;
        } else {
          reward = -2; // махать киркой в пустоту — плохо
        }
        break;
      case 3:
        reward = -1;   // простаивать — плохо
        break;
    }

    const dAfter = this.nearest() ? Math.abs(this.nearest().x - this.agent.x) : 0;
    reward += dAfter < dBefore ? SHAPE : dAfter > dBefore ? -SHAPE : 0;

    if (reward === 0) reward = -0.25; // лёгкий штраф за шаг без результата

    let done = false, success = false;
    if (this.remaining() === 0) { done = true; success = true; reward += 50; }
    else if (this.epSteps >= this.maxSteps) { done = true; success = false; }

    this.epReward += reward;
    return { reward, done, success, epReward: this.epReward, epSteps: this.epSteps };
  }
}
