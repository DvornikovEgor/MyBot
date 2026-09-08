"""Главный генератор: промпт -> картинка (PNG).

Собирает сцену из слоёв в правильном порядке и применяет стиль
(винтаж/минимализм/неон и т.д.) и подпись.
"""

from __future__ import annotations

import random
from typing import Optional

from . import render as R
from .canvas import Canvas, mix
from .font import draw_text, draw_text_centered, text_width
from .prompt import Scene, parse
from .translit import transliterate

__all__ = ["generate", "render_scene", "TextToImage"]


def render_scene(scene: Scene, width: int = 512, height: int = 512,
                 caption: bool = True) -> Canvas:
    """Нарисовать сцену на холсте и вернуть его."""
    rng = random.Random(scene.seed)
    c = Canvas(width, height, background=scene.palette.sky_top)
    horizon = R._horizon(height, scene)

    # 1) небо
    R.draw_sky(c, scene, rng)
    R.draw_stars(c, scene, rng, horizon)

    # 2) небесные тела
    if scene.has("planet"):
        R.draw_planet(c, scene, rng, horizon)
    if scene.has("moon"):
        R.draw_moon(c, scene, rng, horizon)
    if scene.has("sun") or (scene.palette.name in ("day", "sunset", "dawn") and not scene.has("moon")):
        R.draw_sun(c, scene, rng, horizon)
    if scene.has("clouds") or scene.palette.name == "storm":
        R.draw_clouds(c, scene, rng, horizon)
    if scene.has("rainbow"):
        R.draw_rainbow(c, scene, rng, horizon)
    if scene.has("bird"):
        R.draw_bird(c, scene, rng, horizon)

    # 3) дальний план (горы) до земли
    if scene.has("mountains"):
        R.draw_mountains(c, scene, rng, horizon)

    # 4) земля / вода
    if scene.has("sea"):
        R.draw_sea(c, scene, rng, horizon)
    elif scene.has("desert"):
        R.draw_desert(c, scene, rng, horizon)
    elif scene.has("lake"):
        R.draw_ground(c, scene, rng, horizon)
        R.draw_sea(c, scene, rng, int(height * 0.8))
    else:
        R.draw_ground(c, scene, rng, horizon)
        if scene.has("hills"):
            R.draw_hills(c, scene, rng, horizon)

    # 5) объекты на земле
    if scene.has("city"):
        R.draw_city(c, scene, rng, horizon)
    if scene.has("trees"):
        R.draw_trees(c, scene, rng, horizon)
    if scene.has("house"):
        R.draw_house(c, scene, rng, horizon)
    if scene.has("flower"):
        R.draw_flowers(c, scene, rng, horizon)
    if scene.has("boat") and (scene.has("sea") or scene.has("lake")):
        R.draw_boat(c, scene, rng, horizon)

    # 6) погода поверх
    if scene.has("rain") or scene.palette.name == "storm":
        R.draw_rain(c, scene, rng, horizon)
    if scene.has("snow") or (scene.palette.name == "winter" and scene.has("clouds")):
        R.draw_snow(c, scene, rng, horizon)
    if scene.has("fog"):
        R.draw_fog(c, scene, rng, horizon)

    # 7) стиль
    _apply_style(c, scene, rng)

    # 8) подпись
    if caption:
        _draw_caption(c, scene)

    return c


def _apply_style(c: Canvas, scene: Scene, rng: random.Random) -> None:
    style = scene.style
    if style == "vintage":
        # тёплый сепия-сдвиг + зерно + сильная виньетка
        for y in range(c.height):
            row = c._buf[y]
            for x in range(c.width):
                i = x * 3
                r, g, b = row[i], row[i + 1], row[i + 2]
                row[i] = min(255, int(r * 0.9 + 40))
                row[i + 1] = min(255, int(g * 0.85 + 24))
                row[i + 2] = min(255, int(b * 0.7 + 10))
        c.add_noise(10, rng)
        c.vignette(0.5)
    elif style == "minimal":
        c.vignette(0.15)
    elif style == "dreamy":
        c.add_noise(4, rng)
        c.vignette(0.25)
    else:  # vivid
        c.add_noise(6, rng)
        c.vignette(0.35)


def _draw_caption(c: Canvas, scene: Scene) -> None:
    text = transliterate(scene.prompt).upper()
    if len(text) > 42:
        text = text[:39] + "..."
    scale = 2 if c.width >= 400 else 1
    tw = text_width(text, scale)
    while tw > c.width - 16 and scale > 1:
        scale -= 1
        tw = text_width(text, scale)
    pad = 6
    bar_h = 7 * scale + pad * 2
    y0 = c.height - bar_h
    # полупрозрачная плашка
    c.rect(0, y0, c.width, c.height, (0, 0, 0), alpha=0.45)
    draw_text_centered(c, text, c.width // 2, y0 + pad, (245, 245, 245), scale=scale)


def generate(prompt: str, out_path: str, width: int = 512, height: int = 512,
             seed: Optional[int] = None, caption: bool = True) -> Scene:
    """Сгенерировать картинку по промпту и сохранить в PNG.

    Возвращает разобранную сцену (что именно распознано в промпте).
    """
    scene = parse(prompt, seed=seed)
    canvas = render_scene(scene, width, height, caption=caption)
    canvas.save(out_path)
    return scene


class TextToImage:
    """Удобная обёртка: настраиваешь размер один раз, генеришь много раз."""

    def __init__(self, width: int = 512, height: int = 512, caption: bool = True):
        self.width = width
        self.height = height
        self.caption = caption

    def __call__(self, prompt: str, out_path: str, seed: Optional[int] = None) -> Scene:
        return generate(prompt, out_path, self.width, self.height, seed, self.caption)

    def to_bytes(self, prompt: str, seed: Optional[int] = None) -> bytes:
        scene = parse(prompt, seed=seed)
        canvas = render_scene(scene, self.width, self.height, caption=self.caption)
        return canvas.to_png_bytes()
