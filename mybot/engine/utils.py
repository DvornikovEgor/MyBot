"""Мелкие утилиты: случайность, батчи, метрики, прогресс, работа с файлами."""

from __future__ import annotations

import json
import math
import random
import sys
import time
from typing import Iterable, Iterator, List, Optional, Sequence, Tuple, TypeVar

from .tensor import Tensor

__all__ = [
    "set_seed", "batches", "train_test_split", "accuracy", "sample_from_logits",
    "ProgressBar", "save_checkpoint", "load_checkpoint", "Timer",
]

T = TypeVar("T")


def set_seed(seed: int = 42) -> None:
    """Зафиксировать случайность — эксперименты должны повторяться."""
    random.seed(seed)


def batches(data: Sequence[T], batch_size: int, shuffle: bool = False,
            drop_last: bool = False) -> Iterator[List[T]]:
    """Разрезать последовательность на батчи."""
    idxs = list(range(len(data)))
    if shuffle:
        random.shuffle(idxs)
    for start in range(0, len(idxs), batch_size):
        chunk = idxs[start:start + batch_size]
        if drop_last and len(chunk) < batch_size:
            continue
        yield [data[i] for i in chunk]


def train_test_split(data: Sequence[T], test_ratio: float = 0.2, seed: int = 0):
    """Разбить на обучающую и проверочную части."""
    idxs = list(range(len(data)))
    rnd = random.Random(seed)
    rnd.shuffle(idxs)
    n_test = max(1, int(round(len(idxs) * test_ratio)))
    test = [data[i] for i in idxs[:n_test]]
    train = [data[i] for i in idxs[n_test:]]
    return train, test


def accuracy(logits: Tensor, targets: Sequence[int]) -> float:
    """Доля верных ответов для классификации."""
    preds = logits.argmax(dim=-1)
    correct = sum(1 for p, t in zip(preds, targets) if p == int(t))
    return correct / max(len(targets), 1)


def sample_from_logits(logits: Tensor, temperature: float = 1.0,
                       top_k: Optional[int] = None) -> int:
    """Выбрать индекс из распределения, заданного логитами.

    ``temperature`` < 1 делает выбор более «уверенным», > 1 — более случайным.
    """
    row = [v / max(temperature, 1e-6) for v in logits.data]
    m = max(row)
    exps = [math.exp(v - m) for v in row]
    total = sum(exps)
    probs = [e / total for e in exps]

    if top_k is not None and top_k > 0 and top_k < len(probs):
        order = sorted(range(len(probs)), key=lambda i: probs[i], reverse=True)[:top_k]
        probs = [probs[i] if i in set(order) else 0.0 for i in range(len(probs))]
        probs = [p / sum(probs) for p in probs]

    r = random.random()
    acc = 0.0
    for i, p in enumerate(probs):
        acc += p
        if r <= acc:
            return i
    return len(probs) - 1


class ProgressBar:
    """Простейший текстовый прогресс-бар без зависимостей."""

    def __init__(self, total: int, width: int = 30, stream=sys.stdout):
        self.total = max(int(total), 1)
        self.width = width
        self.stream = stream
        self.start = time.time()
        self.last_len = 0

    def update(self, step: int, info: str = "") -> None:
        frac = min(max(step / self.total, 0.0), 1.0)
        filled = int(self.width * frac)
        bar = "█" * filled + "·" * (self.width - filled)
        elapsed = time.time() - self.start
        line = "\r[%s] %5.1f%% | %s%s" % (
            bar, 100 * frac, _fmt_time(elapsed), (" | " + info) if info else ""
        )
        self.stream.write(line.ljust(self.last_len))
        self.stream.flush()
        self.last_len = len(line)

    def close(self) -> None:
        self.stream.write("\n")
        self.stream.flush()


def _fmt_time(seconds: float) -> str:
    if seconds < 60:
        return "%.1fs" % seconds
    m, s = divmod(int(seconds), 60)
    return "%dm %02ds" % (m, s)


class Timer:
    """Контекстный замер времени."""

    def __init__(self, name: str = "", verbose: bool = True):
        self.name = name
        self.verbose = verbose
        self.elapsed = 0.0

    def __enter__(self):
        self._start = time.time()
        return self

    def __exit__(self, *exc):
        self.elapsed = time.time() - self._start
        if self.verbose:
            print("%s: %.2f с" % (self.name or "время", self.elapsed))
        return False


def clip_grad_norm(params: Iterable[Tensor], max_norm: float = 5.0) -> float:
    """Обрезать градиенты по норме — защита от «взрыва» градиентов в RNN.

    Возвращает норму градиента до обрезки.
    """
    params = [p for p in params if p.grad is not None]
    total_sq = 0.0
    for p in params:
        total_sq += math.fsum(g * g for g in p.grad)
    total = math.sqrt(total_sq)
    if total > max_norm > 0.0:
        scale = max_norm / total
        for p in params:
            p.grad = [g * scale for g in p.grad]
    return total


def save_checkpoint(model, path: str, meta: dict = None) -> None:
    """Сохранить веса (и метаданные) в JSON."""
    payload = {"meta": meta or {}, "state": model.state_dict()}
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f)


def load_checkpoint(model, path: str) -> dict:
    """Загрузить веса из JSON. Возвращает метаданные."""
    with open(path, "r", encoding="utf-8") as f:
        payload = json.load(f)
    model.load_state_dict(payload["state"])
    return payload.get("meta", {})
