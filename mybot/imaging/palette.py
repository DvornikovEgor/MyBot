"""Цвета, палитры и настроение: перевод слов в цветовые схемы.

Понимает русские и английские ключевые слова: времена суток, погоду,
настроение, стили. Возвращает согласованную палитру для сцены.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

Color = Tuple[int, int, int]


@dataclass
class Palette:
    """Набор цветов для одной сцены."""
    sky_top: Color
    sky_bottom: Color
    ground: Color
    ground_shadow: Color
    accent: Color          # солнце/луна/главный объект
    detail: Color          # мелкие детали, звёзды
    silhouette: Color      # горы, деревья на фоне
    name: str = "default"


# базовые палитры по времени суток / атмосфере -----------------------------

PALETTES: Dict[str, Palette] = {
    "day": Palette(
        sky_top=(84, 154, 233), sky_bottom=(188, 224, 255),
        ground=(96, 168, 92), ground_shadow=(60, 120, 66),
        accent=(255, 236, 150), detail=(255, 255, 255),
        silhouette=(70, 110, 120), name="day",
    ),
    "sunset": Palette(
        sky_top=(60, 46, 110), sky_bottom=(255, 150, 90),
        ground=(90, 60, 80), ground_shadow=(50, 34, 54),
        accent=(255, 208, 120), detail=(255, 236, 200),
        silhouette=(38, 24, 44), name="sunset",
    ),
    "night": Palette(
        sky_top=(8, 12, 40), sky_bottom=(30, 34, 78),
        ground=(20, 26, 44), ground_shadow=(10, 14, 26),
        accent=(240, 240, 210), detail=(255, 255, 255),
        silhouette=(6, 8, 22), name="night",
    ),
    "dawn": Palette(
        sky_top=(120, 120, 190), sky_bottom=(255, 200, 170),
        ground=(80, 110, 90), ground_shadow=(48, 70, 58),
        accent=(255, 224, 170), detail=(255, 245, 220),
        silhouette=(64, 72, 96), name="dawn",
    ),
    "storm": Palette(
        sky_top=(40, 44, 54), sky_bottom=(96, 104, 118),
        ground=(52, 60, 56), ground_shadow=(30, 36, 34),
        accent=(220, 226, 235), detail=(250, 250, 120),
        silhouette=(22, 26, 30), name="storm",
    ),
    "space": Palette(
        sky_top=(4, 2, 20), sky_bottom=(24, 8, 48),
        ground=(18, 10, 30), ground_shadow=(8, 4, 16),
        accent=(255, 220, 160), detail=(255, 255, 255),
        silhouette=(40, 20, 60), name="space",
    ),
    "neon": Palette(
        sky_top=(24, 4, 48), sky_bottom=(120, 20, 110),
        ground=(18, 6, 34), ground_shadow=(8, 2, 18),
        accent=(0, 240, 220), detail=(255, 40, 160),
        silhouette=(10, 2, 24), name="neon",
    ),
    "winter": Palette(
        sky_top=(150, 180, 210), sky_bottom=(226, 236, 246),
        ground=(228, 236, 244), ground_shadow=(180, 196, 214),
        accent=(255, 246, 224), detail=(255, 255, 255),
        silhouette=(120, 140, 160), name="winter",
    ),
    "autumn": Palette(
        sky_top=(120, 140, 180), sky_bottom=(220, 210, 190),
        ground=(150, 110, 60), ground_shadow=(96, 70, 40),
        accent=(255, 210, 130), detail=(255, 180, 90),
        silhouette=(110, 70, 40), name="autumn",
    ),
}

# синонимы -> ключ палитры (ru + en) ---------------------------------------

MOOD_WORDS: Dict[str, List[str]] = {
    "day": ["день", "днём", "дневной", "полдень", "day", "noon", "daylight", "солнечный"],
    "sunset": ["закат", "закате", "вечер", "вечером", "sunset", "dusk", "evening", "golden"],
    "night": ["ночь", "ночью", "ночной", "полночь", "night", "midnight", "тёмный", "темный", "dark"],
    "dawn": ["рассвет", "утро", "утром", "заря", "dawn", "sunrise", "morning"],
    "storm": ["буря", "гроза", "шторм", "storm", "thunder", "гром", "молния", "lightning", "пасмурно"],
    "space": ["космос", "космический", "галактика", "space", "galaxy", "cosmos", "nebula", "туманность"],
    "neon": ["неон", "неоновый", "киберпанк", "neon", "cyberpunk", "synthwave", "ретровейв"],
    "winter": ["зима", "зимой", "зимний", "снег", "снежный", "winter", "snow", "snowy", "мороз", "ice", "лёд"],
    "autumn": ["осень", "осенний", "autumn", "fall", "листопад"],
}

WARM_WORDS = ["тёплый", "теплый", "warm", "уютный", "cozy", "радость", "счастье", "happy", "joy"]
COLD_WORDS = ["холодный", "cold", "cool", "грусть", "sad", "печаль", "melancholy", "одиночество"]

# именованные цвета (ru + en) ----------------------------------------------

NAMED_COLORS: Dict[str, Color] = {
    "red": (220, 60, 60), "красный": (220, 60, 60),
    "orange": (240, 150, 60), "оранжевый": (240, 150, 60),
    "yellow": (245, 220, 90), "жёлтый": (245, 220, 90), "желтый": (245, 220, 90),
    "green": (80, 190, 100), "зелёный": (80, 190, 100), "зеленый": (80, 190, 100),
    "blue": (70, 130, 220), "синий": (70, 130, 220), "голубой": (120, 190, 240),
    "purple": (150, 90, 210), "фиолетовый": (150, 90, 210), "violet": (150, 90, 210),
    "pink": (240, 130, 190), "розовый": (240, 130, 190),
    "white": (245, 245, 250), "белый": (245, 245, 250),
    "black": (24, 24, 28), "чёрный": (24, 24, 28), "черный": (24, 24, 28),
    "gold": (230, 190, 90), "золотой": (230, 190, 90),
    "teal": (60, 180, 180), "бирюзовый": (60, 180, 180),
}


def detect_palette(tokens: List[str], matcher=None) -> Palette:
    """Определить палитру по словам. По умолчанию — день.

    ``matcher(words, tokens) -> bool`` — необязательная функция сопоставления
    (например, со стеммингом); если не задана, сравнение точное.
    """
    scores: Dict[str, int] = {}
    for key, words in MOOD_WORDS.items():
        if matcher is not None:
            scores[key] = sum(1 for w in words if matcher([w], tokens))
        else:
            scores[key] = sum(1 for w in words if w in tokens)
    best = max(scores, key=lambda k: scores[k])
    if scores[best] == 0:
        best = "day"
    return PALETTES[best]


def detect_named_color(tokens: List[str]) -> Optional[Color]:
    for t in tokens:
        if t in NAMED_COLORS:
            return NAMED_COLORS[t]
    return None
