// Seeded pseudo-random number generator (mulberry32) for reproducible compositions.

export function hashString(str) {
  let h = 0x811c9dc5;
  for (let i = 0; i < str.length; i++) {
    h ^= str.charCodeAt(i);
    h = Math.imul(h, 0x01000193);
  }
  return h >>> 0;
}

export class Rng {
  constructor(seed) {
    this.s = (typeof seed === 'string' ? hashString(seed) : seed >>> 0) || 1;
  }

  /** Uniform float in [0, 1). */
  next() {
    let t = (this.s += 0x6d2b79f5);
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  }

  /** Uniform integer in [min, max] inclusive. */
  int(min, max) {
    return min + Math.floor(this.next() * (max - min + 1));
  }

  /** Uniform float in [min, max). */
  float(min, max) {
    return min + this.next() * (max - min);
  }

  pick(arr) {
    return arr[Math.floor(this.next() * arr.length)];
  }

  chance(p) {
    return this.next() < p;
  }

  /** Weighted pick. entries: [[value, weight], ...] */
  weighted(entries) {
    let total = 0;
    for (const e of entries) total += e[1];
    let r = this.next() * total;
    for (const e of entries) {
      r -= e[1];
      if (r <= 0) return e[0];
    }
    return entries[entries.length - 1][0];
  }

  /** Approximately normal sample (sum of uniforms), mean 0 stddev ~1. */
  gauss() {
    return (this.next() + this.next() + this.next() + this.next() + this.next() + this.next() - 3) / 1.2247;
  }

  shuffle(arr) {
    const a = arr.slice();
    for (let i = a.length - 1; i > 0; i--) {
      const j = Math.floor(this.next() * (i + 1));
      [a[i], a[j]] = [a[j], a[i]];
    }
    return a;
  }
}
