"""Генератор текста на цепях Маркова.

Используется только стандартная библиотека — никаких внешних зависимостей
и никаких сетевых запросов.
"""

import random
import re

_WORD_RE = re.compile(r"[а-яa-zё0-9]+(?:[-'][а-яa-zё0-9]+)*", re.IGNORECASE)


def tokenize(text):
    """Разбивает текст на слова (нижний регистр)."""
    return [t.lower() for t in _WORD_RE.findall(text or "")]


class MarkovChain:
    """Простая цепь Маркова порядка `order` для генерации связного текста."""

    def __init__(self, order=1):
        self.order = max(1, int(order))
        self._transitions = {}
        self._starts = []

    def train(self, corpus_text):
        """Обучает цепь на тексте (любые ответы бота, заметки и т.п.)."""
        for sentence in re.split(r"[.!?…]+", corpus_text or ""):
            tokens = tokenize(sentence)
            if len(tokens) < 2:
                continue
            self._starts.append(tuple(tokens[: self.order]))
            for i in range(len(tokens) - self.order):
                state = tuple(tokens[i : i + self.order])
                nxt = tokens[i + self.order]
                self._transitions.setdefault(state, []).append(nxt)

    def generate(self, max_words=14):
        """Сочиняет фразу или возвращает None, если обучать не на чем."""
        if not self._starts or not self._transitions:
            return None
        words = list(random.choice(self._starts))
        for _ in range(max_words - len(words)):
            state = tuple(words[-self.order:])
            options = self._transitions.get(state)
            if not options:
                break
            words.append(random.choice(options))
        text = " ".join(words)
        return text.capitalize() + random.choice((".", "!", "…"))
