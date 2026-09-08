"""Работа с текстом: символы, словарь, обучающие последовательности."""

from __future__ import annotations

import random
from pathlib import Path
from typing import Iterable, List, Sequence, Tuple

__all__ = ["CharVocab", "TextDataset", "load_text", "DEFAULT_CORPUS_PATH"]

DEFAULT_CORPUS_PATH = Path(__file__).with_name("corpus_ru.txt")


def load_text(path: str = None, lower: bool = True) -> str:
    """Прочитать текст для обучения. По умолчанию — встроенный русский корпус."""
    target = Path(path) if path else DEFAULT_CORPUS_PATH
    if not target.exists():
        raise FileNotFoundError("текст не найден: %s" % target)
    text = target.read_text(encoding="utf-8")
    return text.lower() if lower else text


class CharVocab:
    """Отображение «символ <-> номер» для символьной модели."""

    def __init__(self, chars: Iterable[str]):
        chars = list(dict.fromkeys(chars))          # сохраняем порядок, убираем дубли
        if not chars:
            raise ValueError("словарь не может быть пустым")
        self.itos: List[str] = chars
        self.stoi = {ch: i for i, ch in enumerate(chars)}

    @classmethod
    def from_text(cls, text: str, min_count: int = 1) -> "CharVocab":
        counts = {}
        for ch in text:
            counts[ch] = counts.get(ch, 0) + 1
        chars = [ch for ch, n in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
                 if n >= min_count]
        # частые символы вперёд: так проще отлаживать, порядок всё равно не важен
        return cls(chars)

    def encode(self, text: str) -> List[int]:
        """Строка -> список номеров (неизвестные символы пропускаются)."""
        return [self.stoi[ch] for ch in text if ch in self.stoi]

    def decode(self, ids: Sequence[int]) -> str:
        """Список номеров -> строка."""
        return "".join(self.itos[int(i)] for i in ids if 0 <= int(i) < len(self.itos))

    def __len__(self) -> int:
        return len(self.itos)

    def __repr__(self) -> str:
        preview = "".join(self.itos[:40])
        return "CharVocab(%d символов: %r...)" % (len(self.itos), preview)

    # --- сохранение/загрузка ----------------------------------------------

    def to_dict(self) -> dict:
        return {"chars": self.itos}

    @classmethod
    def from_dict(cls, blob: dict) -> "CharVocab":
        return cls(blob["chars"])


class TextDataset:
    """Нарезает закодированный текст на пары (вход, цель) длины `seq_len`."""

    def __init__(self, ids: Sequence[int], seq_len: int):
        if len(ids) <= seq_len:
            raise ValueError("текст слишком короткий для такой длины последовательности")
        self.ids = list(ids)
        self.seq_len = int(seq_len)

    def __len__(self) -> int:
        return len(self.ids) - self.seq_len

    def __getitem__(self, index: int) -> Tuple[List[int], List[int]]:
        if index < 0:
            index += len(self)
        chunk = self.ids[index:index + self.seq_len + 1]
        return chunk[:-1], chunk[1:]

    def random_item(self, rng: random.Random = None) -> Tuple[List[int], List[int]]:
        rng = rng or random
        return self[rng.randrange(len(self))]

    def __repr__(self) -> str:
        return "TextDataset(%d примеров, seq_len=%d)" % (len(self), self.seq_len)
