"""Символьная рекуррентная сеть (char-level RNN) — маленькая языковая модель.

Она предсказывает следующий символ по предыдущим, учится на обычном тексте
и умеет генерировать продолжение. Классическая схема из курса CS231n,
только реализованная на чистом Python.
"""

from __future__ import annotations

import random
from typing import List, Optional, Sequence

from ..engine.functional import cross_entropy
from ..engine.nn import Linear, Module, RNNCell
from ..engine.tensor import Tensor, no_grad
from ..engine.utils import sample_from_logits

__all__ = ["CharRNN", "one_hot_input"]


def one_hot_input(vocab_size: int, index: int) -> Tensor:
    """One-hot вектор строки (1, vocab_size) — вход одного шага сети."""
    data = [0.0] * vocab_size
    data[int(index)] = 1.0
    return Tensor(data, (1, vocab_size))


class CharRNN(Module):
    """RNN: один символ на входе, распределение над символами на выходе."""

    def __init__(self, vocab_size: int, hidden_size: int = 64):
        super().__init__()
        self.vocab_size = int(vocab_size)
        self.hidden_size = int(hidden_size)
        self.cell = RNNCell(self.vocab_size, self.hidden_size, nonlinearity="tanh")
        self.h2y = Linear(self.hidden_size, self.vocab_size)

    def init_hidden(self, batch_size: int = 1) -> Tensor:
        return Tensor([0.0] * (batch_size * self.hidden_size), (batch_size, self.hidden_size))

    def step(self, x: Tensor, h: Tensor):
        """Один шаг: (x, h) -> (логиты, новое состояние)."""
        h_new = self.cell(x, h)
        return self.h2y(h_new), h_new

    def forward(self, xs: Sequence[Tensor], h: Optional[Tensor] = None):
        """Прямой проход по последовательности one-hot входов.

        Возвращает список логитов (по одному на шаг) и финальное состояние.
        """
        if h is None:
            h = self.init_hidden(xs[0].shape[0] if xs else 1)
        logits: List[Tensor] = []
        for x in xs:
            y, h = self.step(x, h)
            logits.append(y)
        return logits, h

    def sequence_loss(self, logits: Sequence[Tensor], targets: Sequence[int]) -> Tensor:
        """Средняя кросс-энтропия по шагам последовательности."""
        total: Optional[Tensor] = None
        for y, t in zip(logits, targets):
            loss = cross_entropy(y, [int(t)])
            total = loss if total is None else total + loss
        if total is None:
            raise ValueError("пустая последовательность")
        return total / len(logits)

    # --- генерация ---------------------------------------------------------

    @staticmethod
    def _warm_up(model: "CharRNN", ids: Sequence[int], h: Tensor) -> Tensor:
        for i in ids:
            _, h = model.step(one_hot_input(model.vocab_size, i), h)
        return h

    def generate(self, vocab, prompt: str = "", length: int = 200,
                 temperature: float = 0.8, top_k: Optional[int] = None,
                 stop: Optional[str] = None) -> str:
        """Продолжить текст `prompt` на `length` символов."""
        with no_grad():
            ids = vocab.encode(prompt) if isinstance(prompt, str) else list(prompt)
            h = self.init_hidden()
            if ids:
                h = self._warm_up(self, ids, h)
                last = ids[-1]
            else:
                last = random.randrange(self.vocab_size)
            out_ids: List[int] = []
            for _ in range(length):
                x = one_hot_input(self.vocab_size, last)
                logits, h = self.step(x, h)
                last = sample_from_logits(logits, temperature=temperature, top_k=top_k)
                out_ids.append(last)
                if stop is not None:
                    text = vocab.decode(out_ids)
                    if text.endswith(stop):
                        break
        return vocab.decode(out_ids)

    def __repr__(self) -> str:
        return "CharRNN(vocab=%d, hidden=%d)" % (self.vocab_size, self.hidden_size)
