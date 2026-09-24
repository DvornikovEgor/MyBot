// Карта пруда: комнаты, коридоры, норы (вентиляция), задания, точки починки.
// Модуль чистый — без DOM, пригоден для тестов в Node.

export const ROOMS = [
  { id: 'lily',    name: 'Кувшинки',  x: 100,  y: 100,  w: 420, h: 300, floor: '#2c5f3c', kind: 'grass' },
  { id: 'reeds',   name: 'Камыши',    x: 620,  y: 100,  w: 400, h: 280, floor: '#2a5638', kind: 'reeds' },
  { id: 'green',   name: 'Оранжерея', x: 1120, y: 100,  w: 460, h: 300, floor: '#2e6a41', kind: 'glass' },
  { id: 'store',   name: 'Кладовая',  x: 1660, y: 140,  w: 360, h: 300, floor: '#4a4030', kind: 'wood' },
  { id: 'pond',    name: 'Пруд',      x: 100,  y: 520,  w: 520, h: 420, floor: '#22606b', kind: 'water' },
  { id: 'med',     name: 'Медпункт',  x: 820,  y: 520,  w: 360, h: 300, floor: '#3d5c52', kind: 'tile' },
  { id: 'pump',    name: 'Насос',     x: 1360, y: 560,  w: 380, h: 300, floor: '#4a4a3a', kind: 'metal' },
  { id: 'deck',    name: 'Терраса',   x: 100,  y: 1040, w: 460, h: 280, floor: '#514330', kind: 'wood' },
  { id: 'compost', name: 'Компост',   x: 760,  y: 1000, w: 420, h: 320, floor: '#4b3a26', kind: 'dirt' },
  { id: 'swamp',   name: 'Болото',    x: 1420, y: 1000, w: 480, h: 320, floor: '#2f4f33', kind: 'mud' },
];

// Коридоры соединяют комнаты; смежность считается по пересечению прямоугольников.
export const CORRIDORS = [
  { id: 'c1',  x: 520,  y: 180,  w: 100, h: 120 }, // Кувшинки — Камыши
  { id: 'c2',  x: 1020, y: 180,  w: 100, h: 120 }, // Камыши — Оранжерея
  { id: 'c3',  x: 1580, y: 220,  w: 80,  h: 120 }, // Оранжерея — Кладовая
  { id: 'c4',  x: 240,  y: 400,  w: 120, h: 120 }, // Кувшинки — Пруд
  { id: 'c5',  x: 760,  y: 380,  w: 120, h: 140 }, // Камыши — Медпункт
  { id: 'c6',  x: 1020, y: 400,  w: 140, h: 120 }, // Оранжерея — Медпункт
  { id: 'c7',  x: 1400, y: 400,  w: 120, h: 160 }, // Оранжерея — Насос
  { id: 'c8',  x: 1700, y: 440,  w: 120, h: 120 }, // Кладовая — Насос
  { id: 'c9',  x: 620,  y: 600,  w: 200, h: 120 }, // Пруд — Медпункт
  { id: 'c10', x: 1180, y: 620,  w: 180, h: 120 }, // Медпункт — Насос
  { id: 'c11', x: 300,  y: 940,  w: 140, h: 100 }, // Пруд — Терраса
  { id: 'c12', x: 920,  y: 820,  w: 140, h: 180 }, // Медпункт — Компост
  { id: 'c13', x: 1560, y: 860,  w: 140, h: 140 }, // Насос — Болото
  { id: 'c14', x: 560,  y: 1080, w: 200, h: 120 }, // Терраса — Компост
  { id: 'c15', x: 1180, y: 1080, w: 240, h: 120 }, // Компост — Болото
];

// Норы (аналог вентиляции): прыжок между парными точками.
export const VENTS = [
  { id: 'v1', x: 470,  y: 360,  to: 'v2' },
  { id: 'v2', x: 970,  y: 340,  to: 'v1' },
  { id: 'v3', x: 1540, y: 360,  to: 'v4' },
  { id: 'v4', x: 1980, y: 400,  to: 'v3' },
  { id: 'v5', x: 580,  y: 900,  to: 'v6' },
  { id: 'v6', x: 1140, y: 780,  to: 'v5' },
  { id: 'v7', x: 1140, y: 1280, to: 'v9' },
  { id: 'v8', x: 1860, y: 1280, to: 'v10' },
  { id: 'v9', x: 1700, y: 820,  to: 'v7' },
  { id: 'v10', x: 800, y: 1060, to: 'v8' },
];

export const TASKS = [
  { id: 't1',  name: 'Поймать мух',          x: 1900, y: 200,  room: 'store' },
  { id: 't2',  name: 'Полить кувшинки',      x: 170,  y: 150,  room: 'lily' },
  { id: 't3',  name: 'Настроить квак-связь', x: 680,  y: 150,  room: 'reeds' },
  { id: 't4',  name: 'Взвесить икру',        x: 1200, y: 150,  room: 'green' },
  { id: 't5',  name: 'Очистить воду',        x: 150,  y: 880,  room: 'pond' },
  { id: 't6',  name: 'Убрать слизь',         x: 900,  y: 560,  room: 'med' },
  { id: 't7',  name: 'Починить насос',       x: 1420, y: 610,  room: 'pump' },
  { id: 't8',  name: 'Постричь ряску',       x: 150,  y: 1090, room: 'deck' },
  { id: 't9',  name: 'Проверить компост',    x: 1000, y: 1280, room: 'compost' },
  { id: 't10', name: 'Заменить фильтр',      x: 1470, y: 1050, room: 'swamp' },
  { id: 't11', name: 'Разложить икринки',    x: 400,  y: 880,  room: 'pond' },
  { id: 't12', name: 'Покормить головастиков', x: 1620, y: 1280, room: 'swamp' },
];

// Станции починки саботажей.
export const FIX_STATIONS = [
  { id: 'switch', name: 'Рубильник',   x: 560, y: 560, fixes: 'fog',   room: 'pond' },
  { id: 'antenna', name: 'Квак-антенна', x: 980, y: 200, fixes: 'comms', room: 'reeds' },
];

// Кнопка экстренного сбора — большая кувшинка в Пруду.
export const EMERGENCY_PAD = { id: 'pad', name: 'Большая кувшинка', x: 360, y: 730 };

export const SPAWNS = [
  { x: 260, y: 700 }, { x: 330, y: 780 }, { x: 400, y: 690 }, { x: 200, y: 800 },
  { x: 460, y: 790 }, { x: 300, y: 640 }, { x: 380, y: 860 }, { x: 230, y: 880 },
  { x: 480, y: 660 }, { x: 520, y: 850 }, { x: 170, y: 700 }, { x: 420, y: 890 },
];

export const AREAS = [...ROOMS, ...CORRIDORS];

function rectsOverlap(a, b, pad = 2) {
  return (
    a.x < b.x + b.w + pad &&
    b.x < a.x + a.w + pad &&
    a.y < b.y + b.h + pad &&
    b.y < a.y + a.h + pad
  );
}

export function rectAt(x, y, areas = AREAS) {
  for (const r of areas) {
    if (x >= r.x && x <= r.x + r.w && y >= r.y && y <= r.y + r.h) return r;
  }
  return null;
}

export function roomAt(x, y, rooms = ROOMS) {
  for (const r of rooms) {
    if (x >= r.x && x <= r.x + r.w && y >= r.y && y <= r.y + r.h) return r;
  }
  return null;
}

export function walkableAt(x, y, areas = AREAS) {
  return rectAt(x, y, areas) !== null;
}

/** Можно ли находиться в точке (x, y) кругу радиуса r — проверяем обвод по кругу. */
export function canStand(x, y, r = 0, areas = AREAS) {
  if (r <= 0) return walkableAt(x, y, areas);
  for (let i = 0; i < 8; i++) {
    const a = (i / 8) * Math.PI * 2;
    if (!walkableAt(x + Math.cos(a) * r, y + Math.sin(a) * r, areas)) return false;
  }
  return walkableAt(x, y, areas);
}

/** Случайная проходимая точка внутри указанной зоны. */
export function randomPointIn(area, rng, r = 0, areas = AREAS) {
  for (let i = 0; i < 40; i++) {
    const x = rng.range(area.x + r + 2, area.x + area.w - r - 2);
    const y = rng.range(area.y + r + 2, area.y + area.h - r - 2);
    if (canStand(x, y, r, areas)) return { x, y };
  }
  return { x: area.x + area.w / 2, y: area.y + area.h / 2 };
}

// --- Граф смежности зон и поиск пути (BFS) ---
export function buildGraph(areas = AREAS) {
  const adj = new Map();
  for (const a of areas) adj.set(a.id, []);
  for (let i = 0; i < areas.length; i++) {
    for (let j = i + 1; j < areas.length; j++) {
      if (rectsOverlap(areas[i], areas[j])) {
        adj.get(areas[i].id).push(areas[j].id);
        adj.get(areas[j].id).push(areas[i].id);
      }
    }
  }
  return adj;
}

export const GRAPH = buildGraph();

export function areaOfPoint(x, y, areas = AREAS) {
  const r = rectAt(x, y, areas);
  return r ? r.id : null;
}

/** Маршрут по центрам зон от точки A до точки B. Возвращает массив {x,y} (без стартовой точки). */
export function findPath(fromX, fromY, toX, toY, graph = GRAPH, areas = AREAS) {
  const byId = new Map(areas.map((a) => [a.id, a]));
  const start = areaOfPoint(fromX, fromY, areas);
  const goal = areaOfPoint(toX, toY, areas);
  if (!start || !goal) return [{ x: toX, y: toY }];
  if (start === goal) return [{ x: toX, y: toY }];

  const prev = new Map([[start, null]]);
  const queue = [start];
  while (queue.length) {
    const cur = queue.shift();
    if (cur === goal) break;
    for (const next of graph.get(cur) || []) {
      if (!prev.has(next)) {
        prev.set(next, cur);
        queue.push(next);
      }
    }
  }
  if (!prev.has(goal)) return [{ x: toX, y: toY }];

  const ids = [];
  for (let cur = goal; cur !== null && cur !== start; cur = prev.get(cur)) ids.unshift(cur);
  const pts = ids.map((id) => {
    const a = byId.get(id);
    return { x: a.x + a.w / 2, y: a.y + a.h / 2 };
  });
  pts.push({ x: toX, y: toY });
  return pts;
}

/** Все зоны, достижимые из стартовой (для проверки связности карты). */
export function reachableFrom(startId, graph = GRAPH) {
  const seen = new Set([startId]);
  const stack = [startId];
  while (stack.length) {
    const cur = stack.pop();
    for (const next of graph.get(cur) || []) {
      if (!seen.has(next)) {
        seen.add(next);
        stack.push(next);
      }
    }
  }
  return seen;
}

export function ventById(id) {
  return VENTS.find((v) => v.id === id) || null;
}

export function taskById(id) {
  return TASKS.find((t) => t.id === id) || null;
}

export function nearestVent(x, y) {
  let best = null;
  let bestD = Infinity;
  for (const v of VENTS) {
    const d = Math.hypot(v.x - x, v.y - y);
    if (d < bestD) {
      bestD = d;
      best = v;
    }
  }
  return best ? { vent: best, dist: bestD } : null;
}

/**
 * Собрать объект мира из данных карты. Тесты могут передать свою маленькую карту,
 * игра — дефолтный WORLD ниже.
 */
export function createWorld(data) {
  const areas = [...data.rooms, ...data.corridors];
  const graph = buildGraph(areas);
  return {
    width: data.width || 2100,
    height: data.height || 1400,
    rooms: data.rooms,
    corridors: data.corridors,
    vents: data.vents,
    tasks: data.tasks,
    fixStations: data.fixStations,
    emergencyPad: data.emergencyPad,
    spawns: data.spawns,
    areas,
    graph,
    rectAt: (x, y) => rectAt(x, y, areas),
    roomAt: (x, y) => roomAt(x, y, data.rooms),
    walkableAt: (x, y) => walkableAt(x, y, areas),
    canStand: (x, y, r = 0) => canStand(x, y, r, areas),
    randomPointIn: (area, rng, r = 0) => randomPointIn(area, rng, r, areas),
    areaOfPoint: (x, y) => areaOfPoint(x, y, areas),
    findPath: (fx, fy, tx, ty) => findPath(fx, fy, tx, ty, graph, areas),
    ventById: (id) => data.vents.find((v) => v.id === id) || null,
    taskById: (id) => data.tasks.find((t) => t.id === id) || null,
    nearestVent: (x, y) => {
      let best = null;
      let bestD = Infinity;
      for (const v of data.vents) {
        const d = Math.hypot(v.x - x, v.y - y);
        if (d < bestD) {
          bestD = d;
          best = v;
        }
      }
      return best ? { vent: best, dist: bestD } : null;
    },
    roomNameAt: (x, y) => {
      const r = roomAt(x, y, data.rooms);
      return r ? r.name : 'Коридор';
    },
  };
}

export const WORLD = createWorld({
  width: 2100,
  height: 1400,
  rooms: ROOMS,
  corridors: CORRIDORS,
  vents: VENTS,
  tasks: TASKS,
  fixStations: FIX_STATIONS,
  emergencyPad: EMERGENCY_PAD,
  spawns: SPAWNS,
});
