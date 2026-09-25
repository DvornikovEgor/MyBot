// MCAgent — обучение с подкреплением (табличный Q-learning).
// Состояние мира — набор признаков (State → {sdx, inFront}),
// действия — 4 дискретных хода. Агент максимизирует суммарную награду.

export const ACTION_COUNT = 4;
export const ACTION_LABELS = ['←', '→', '⛏', '·'];
export const ACTION_NAMES = ['влево', 'вправо', 'добыть', 'стоять'];

export class MCAgent {
  constructor() {
    this.q = new Map();      // stateKey -> Float64Array(ACTION_COUNT)
    this.visits = new Map(); // stateKey -> число визитов
    this.visitCache = [];    // ключи всех состояний (для тепловой карты)
    this.stats = { seen: 0 };
  }

  key(state) {
    return state.sdx + '|' + state.inFront;
  }

  qValues(state) {
    const key = this.key(state);
    let q = this.q.get(key);
    if (!q) {
      q = new Float64Array(ACTION_COUNT);
      this.q.set(key, q);
      this.visits.set(key, 0);
      this.visitCache.push(key);
      this.stats.seen = this.q.size;
    }
    return q;
  }

  // ε-greedy выбор действия. При равенстве значений — случайно среди лучших.
  act(state, epsilon, rnd) {
    const q = this.qValues(state);
    if (rnd() < epsilon) return (rnd() * ACTION_COUNT) | 0;

    let best = 0;
    const ties = [0];
    for (let a = 1; a < ACTION_COUNT; a++) {
      if (q[a] > q[best]) { best = a; ties.length = 0; ties.push(a); }
      else if (q[a] === q[best]) ties.push(a);
    }
    return ties[(rnd() * ties.length) | 0];
  }

  bestAction(state) {
    const q = this.qValues(state);
    let best = 0;
    for (let a = 1; a < ACTION_COUNT; a++) if (q[a] > q[best]) best = a;
    return best;
  }

  learn(state, action, reward, nextState, alpha, gamma) {
    const q = this.qValues(state);
    const nextQ = this.qValues(nextState);
    const key = this.key(state);
    this.visits.set(key, this.visits.get(key) + 1);

    let maxNext = nextQ[0];
    for (let a = 1; a < ACTION_COUNT; a++) if (nextQ[a] > maxNext) maxNext = nextQ[a];

    q[action] += alpha * (reward + gamma * maxNext - q[action]);
  }

  export() {
    const data = {};
    for (const k of this.visitCache) {
      data[k] = { q: Array.from(this.q.get(k)), v: this.visits.get(k) };
    }
    return JSON.stringify({ v: 1, actions: ACTION_COUNT, states: data });
  }

  import(json) {
    let obj;
    try { obj = JSON.parse(json); } catch { return false; }
    if (!obj || !obj.states) return false;
    this.q.clear();
    this.visits.clear();
    this.visitCache.length = 0;
    for (const k of Object.keys(obj.states)) {
      const st = obj.states[k];
      if (!Array.isArray(st.q) || st.q.length !== ACTION_COUNT) continue;
      this.q.set(k, Float64Array.from(st.q));
      this.visits.set(k, st.v || 0);
      this.visitCache.push(k);
    }
    this.stats.seen = this.q.size;
    return true;
  }

  reset() {
    this.q.clear();
    this.visits.clear();
    this.visitCache.length = 0;
    this.stats.seen = 0;
  }
}
