"""Разбор текстового промпта в структурированное описание сцены.

Никаких ML тут нет — это правила и словари, но их достаточно, чтобы связно
«понять» короткое описание на русском или английском и превратить его в
набор объектов для рисования.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set

from .palette import Palette, detect_named_color, detect_palette

# --- какие объекты умеет рисовать движок и их слова-триггеры ---------------

OBJECT_WORDS: Dict[str, List[str]] = {
    "sun": ["солнце", "солнца", "солнечный", "sun", "sunny", "sunshine"],
    "moon": ["луна", "луны", "месяц", "moon", "lunar", "crescent"],
    "stars": ["звезда", "звёзды", "звезды", "звёздное", "star", "stars", "starry"],
    "mountains": ["гора", "горы", "горах", "mountain", "mountains", "peak", "хребет"],
    "trees": ["дерево", "деревья", "лес", "лесу", "tree", "trees", "forest", "ёлка", "ель", "сосна"],
    "sea": ["море", "моря", "океан", "sea", "ocean", "waves", "волны", "вода"],
    "lake": ["озеро", "озера", "пруд", "lake", "pond"],
    "clouds": ["облако", "облака", "туча", "тучи", "cloud", "clouds", "cloudy"],
    "rain": ["дождь", "дождём", "ливень", "rain", "rainy", "drizzle"],
    "snow": ["снег", "снегопад", "snow", "snowfall", "snowflakes", "снежинки"],
    "house": ["дом", "дома", "домик", "house", "home", "cabin", "хижина", "изба"],
    "city": ["город", "города", "мегаполис", "city", "skyline", "небоскрёбы", "здания", "buildings"],
    "flower": ["цветок", "цветы", "flower", "flowers", "тюльпан", "роза", "поле"],
    "bird": ["птица", "птицы", "bird", "birds", "чайка", "seagull"],
    "boat": ["лодка", "корабль", "парус", "boat", "ship", "sailboat", "яхта"],
    "planet": ["планета", "планеты", "planet", "planets", "сатурн", "saturn"],
    "rainbow": ["радуга", "rainbow"],
    "fog": ["туман", "туманный", "fog", "foggy", "mist", "дымка"],
    "road": ["дорога", "тропа", "путь", "road", "path", "trail", "шоссе"],
    "hills": ["холм", "холмы", "hill", "hills", "поле", "field", "meadow", "луг"],
    "desert": ["пустыня", "пески", "desert", "dune", "dunes", "бархан"],
}

# слова, задающие «плотность»/количество
COUNT_WORDS: Dict[str, int] = {
    "много": 3, "множество": 3, "many": 3, "lots": 3, "куча": 3,
    "несколько": 2, "few": 2, "some": 2, "пара": 2,
    "один": 1, "одна": 1, "одно": 1, "single": 1, "lone": 1, "одинокий": 1,
}

STYLE_WORDS: Dict[str, List[str]] = {
    "minimal": ["минимализм", "минимал", "minimal", "simple", "простой", "flat"],
    "vintage": ["винтаж", "ретро", "vintage", "retro", "старый", "плёнка"],
    "vivid": ["яркий", "сочный", "vivid", "vibrant", "bright", "насыщенный"],
    "dreamy": ["мечтательный", "нежный", "dreamy", "soft", "pastel", "пастель"],
}


@dataclass
class Scene:
    """Структурированное описание того, что нужно нарисовать."""
    prompt: str
    tokens: List[str]
    palette: Palette
    objects: List[str] = field(default_factory=list)
    counts: Dict[str, int] = field(default_factory=dict)
    style: str = "vivid"
    named_color: Optional[tuple] = None
    seed: int = 0

    def has(self, obj: str) -> bool:
        return obj in self.objects

    def count(self, obj: str, default: int = 1) -> int:
        return self.counts.get(obj, default)


_TOKEN_RE = re.compile(r"[a-zA-Zа-яА-ЯёЁ0-9]+")


def tokenize(text: str) -> List[str]:
    return [t.lower() for t in _TOKEN_RE.findall(text)]


def seed_from_text(text: str) -> int:
    """Стабильный сид из текста — один и тот же промпт даёт одну картинку."""
    h = hashlib.sha256(text.strip().lower().encode("utf-8")).hexdigest()
    return int(h[:8], 16)


def _stem(word: str) -> str:
    """Грубый стем: отрезаем типичные русские окончания, чтобы «город»,
    «городом», «города» совпадали. Для коротких слов ничего не режем."""
    if len(word) <= 3:
        return word
    for suf in ("ами", "ями", "ом", "ем", "ах", "ях", "ов", "ев", "ой", "ый",
                "ые", "ье", "ья", "ю", "я", "и", "ы", "е", "а", "о", "у"):
        if word.endswith(suf) and len(word) - len(suf) >= 3:
            return word[: -len(suf)]
    return word


def _matches(words: List[str], tokens: List[str]) -> bool:
    """Совпадение по корню: слово из словаря и токен имеют общий стем.

    Точное совпадение проходит всегда. Иначе сравниваются стемы: равные стемы
    засчитываются, если исходное слово не короче 4 букв (чтобы «море»/«морем»
    совпали); совпадение по префиксу требует общего корня из 4+ букв, чтобы
    «горы» не слиплось с «город»."""
    token_stems = [(t, _stem(t)) for t in tokens]
    for w in words:
        if w in tokens:
            return True
        if len(w) < 4:
            continue
        ws = _stem(w)
        for t, ts in token_stems:
            if len(ts) >= 3 and ws == ts:
                return True
            shorter, longer = (ws, ts) if len(ws) <= len(ts) else (ts, ws)
            if len(shorter) >= 4 and longer.startswith(shorter):
                return True
    return False


def parse(prompt: str, seed: Optional[int] = None) -> Scene:
    """Разобрать промпт в сцену."""
    tokens = tokenize(prompt)
    token_set: Set[str] = set(tokens)

    palette = detect_palette(tokens, matcher=_matches)

    objects: List[str] = []
    counts: Dict[str, int] = {}
    for obj, words in OBJECT_WORDS.items():
        if _matches(words, tokens):
            objects.append(obj)

    # количество: смотрим слово-числитель рядом (упрощённо — по всему промпту)
    global_count = None
    for w, n in COUNT_WORDS.items():
        if w in token_set:
            global_count = n
            break
    if global_count is not None:
        for obj in objects:
            counts[obj] = global_count

    style = "vivid"
    for st, words in STYLE_WORDS.items():
        if any(w in token_set for w in words):
            style = st
            break

    named = detect_named_color(tokens)

    return Scene(
        prompt=prompt.strip(),
        tokens=tokens,
        palette=palette,
        objects=objects,
        counts=counts,
        style=style,
        named_color=named,
        seed=seed if seed is not None else seed_from_text(prompt),
    )
