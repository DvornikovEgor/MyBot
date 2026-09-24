// Чистые игровые правила: раздача заданий, подсчёт голосов, условия победы, решения ботов.

/** Раздать каждому игроку набор заданий (у самозванца они бутафорские). */
export function assignTasks(players, allTasks, perPlayer, rng) {
  const ids = allTasks.map((t) => t.id);
  const out = new Map();
  for (const p of players) {
    const picks = rng.shuffle(ids).slice(0, Math.min(perPlayer, ids.length));
    out.set(
      p.id,
      picks.map((id) => ({ id, done: false, progress: 0 })),
    );
  }
  return out;
}

/** Сколько заданий выполнено у мирных жителей (самозванцы не считаются). */
export function taskProgressOfCrew(players, tasksByPlayer) {
  let done = 0;
  let total = 0;
  for (const p of players) {
    if (p.role === 'impostor') continue;
    const list = tasksByPlayer.get(p.id) || [];
    total += list.length;
    done += list.filter((t) => t.done).length;
  }
  return { done, total, ratio: total ? done / total : 0 };
}

/**
 * Подсчёт голосов.
 * votes: Map<voterId, targetId|null> (null = пропуск).
 * aliveIds — кто ещё в игре и имеет право голоса.
 * Возвращает { counts, skip, ejectedId, tie, max }
 */
export function tallyVotes(votes, aliveIds) {
  const counts = new Map(aliveIds.map((id) => [id, 0]));
  let skip = 0;
  for (const [, target] of votes) {
    if (target === null || target === undefined) skip += 1;
    else if (counts.has(target)) counts.set(target, counts.get(target) + 1);
  }
  let max = skip;
  for (const c of counts.values()) if (c > max) max = c;
  const leaders = [...counts.entries()].filter(([, c]) => c === max && max > 0).map(([id]) => id);
  const tie = leaders.length !== 1 || (skip >= max && max > 0);
  return {
    counts,
    skip,
    max,
    ejectedId: tie ? null : leaders[0],
    tie,
  };
}

/** Живые игроки по ролям. */
export function aliveCounts(players) {
  let crew = 0;
  let impostor = 0;
  for (const p of players) {
    if (!p.alive) continue;
    if (p.role === 'impostor') impostor += 1;
    else crew += 1;
  }
  return { crew, impostor, total: crew + impostor };
}

/**
 * Проверка конца игры.
 * Возвращает { over, winner: 'crew'|'impostor', reason } либо { over: false }.
 */
export function checkWin(players, crewTasks) {
  const { crew, impostor } = aliveCounts(players);
  if (impostor === 0) {
    return { over: true, winner: 'crew', reason: 'Все самозванцы выброшены с кочки!' };
  }
  if (crew <= impostor) {
    return { over: true, winner: 'impostor', reason: 'Самозванцев стало не меньше, чем мирных лягушек.' };
  }
  if (crewTasks.total > 0 && crewTasks.done >= crewTasks.total) {
    return { over: true, winner: 'crew', reason: 'Все задания пруда выполнены!' };
  }
  return { over: false, winner: null, reason: '' };
}

/** Кто видел убийство (свидетели). Сам самозванец и сидящие в норах не в счёт. */
export function witnessesOf(kill, players, range) {
  return players.filter((p) => {
    if (!p.alive || p.vented) return false;
    if (p.id === kill.killerId || p.id === kill.victimId) return false;
    if (p.role === 'impostor' && kill.killerIsImpostor) return false;
    const d = Math.hypot(p.x - kill.x, p.y - kill.y);
    return d <= range;
  });
}

/**
 * Решение бота на голосовании.
 * memory — что бот знает: { sawKill: Set<killerId>, nearBody: Set<killerId> }
 */
export function botVote(bot, alivePlayers, memory, rng) {
  const suspects = [...(memory.sawKill || []), ...(memory.nearBody || [])];
  const validSuspects = suspects.filter((id) =>
    alivePlayers.some((p) => p.id === id && p.id !== bot.id),
  );
  if (validSuspects.length && rng.chance(0.85)) return rng.pick(validSuspects);
  if (rng.chance(0.22)) return null; // пропуск
  const others = alivePlayers.filter((p) => p.id !== bot.id);
  if (!others.length) return null;
  return rng.pick(others).id;
}

/** Финальная фраза после выброса. */
export function ejectText(player, remainingImpostors) {
  const was = player.role === 'impostor';
  const base = `${player.name} ${was ? 'был' : 'не был'} самозванцем`;
  const tail =
    remainingImpostors === 0
      ? 'Самозванцев больше нет.'
      : `Осталось самозванцев: ${remainingImpostors}.`;
  return `${base}. ${tail}`;
}
