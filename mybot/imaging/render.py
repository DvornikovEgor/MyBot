"""Отрисовка сцены: превращает разобранный промпт в картинку.

Каждый объект (солнце, горы, деревья, город...) — отдельная функция рисования.
Композиция строится по слоям: небо -> дальний план -> земля -> объекты -> погода.
"""

from __future__ import annotations

import math
import random
from typing import List, Optional, Tuple

from .canvas import Canvas, Color, mix
from .font import draw_text, draw_text_centered, text_width
from .palette import Palette
from .prompt import Scene, parse

Point = Tuple[float, float]


# ---------------------------------------------------------------------------
# Вспомогательное
# ---------------------------------------------------------------------------


def _adjust(color: Color, factor: float) -> Color:
    return (
        max(0, min(255, int(color[0] * factor))),
        max(0, min(255, int(color[1] * factor))),
        max(0, min(255, int(color[2] * factor))),
    )


def _horizon(height: int, scene: Scene) -> int:
    """Высота линии горизонта. Море/пустыня опускают её ниже."""
    base = int(height * 0.66)
    if scene.has("sea") or scene.has("lake"):
        base = int(height * 0.60)
    if scene.has("city"):
        base = int(height * 0.72)
    return base


# ---------------------------------------------------------------------------
# Слои: небо и фон
# ---------------------------------------------------------------------------


def draw_sky(c: Canvas, scene: Scene, rng: random.Random) -> None:
    p = scene.palette
    c.vertical_gradient(p.sky_top, p.sky_bottom)


def draw_stars(c: Canvas, scene: Scene, rng: random.Random, horizon: int) -> None:
    p = scene.palette
    n = 120 if scene.has("stars") else (60 if p.name in ("night", "space") else 0)
    n *= max(1, scene.count("stars", 1))
    for _ in range(n):
        x = rng.randint(0, c.width - 1)
        y = rng.randint(0, int(horizon * 0.9))
        r = rng.choice([0.5, 0.7, 1.0, 1.3])
        b = rng.uniform(0.5, 1.0)
        c.fill_circle(x, y, r, p.detail, alpha=b, soft=0.7)
    # млечный путь для космоса
    if p.name == "space":
        for _ in range(400):
            x = rng.gauss(c.width * 0.5, c.width * 0.22)
            y = rng.gauss(horizon * 0.4, horizon * 0.12)
            c.fill_circle(x, y, rng.uniform(0.3, 0.9),
                          mix(p.detail, p.accent, rng.random()),
                          alpha=rng.uniform(0.2, 0.6), soft=0.6)


def draw_sun(c: Canvas, scene: Scene, rng: random.Random, horizon: int) -> None:
    p = scene.palette
    cx = c.width * (0.5 + rng.uniform(-0.22, 0.22))
    cy = horizon * (0.42 + rng.uniform(-0.1, 0.1))
    r = min(c.width, c.height) * 0.11
    # мягкое свечение
    for i in range(6, 0, -1):
        glow = _adjust(p.accent, 0.6 + 0.06 * i)
        c.fill_circle(cx, cy, r * (1 + i * 0.35), glow,
                      alpha=0.06, soft=r * 0.5)
    c.fill_circle(cx, cy, r, p.accent, soft=1.5)


def draw_moon(c: Canvas, scene: Scene, rng: random.Random, horizon: int) -> None:
    p = scene.palette
    cx = c.width * (0.5 + rng.uniform(-0.25, 0.25))
    cy = horizon * (0.35 + rng.uniform(-0.08, 0.08))
    r = min(c.width, c.height) * 0.09
    for i in range(5, 0, -1):
        c.fill_circle(cx, cy, r * (1 + i * 0.3), p.accent, alpha=0.05, soft=r * 0.5)
    c.fill_circle(cx, cy, r, p.accent, soft=1.5)
    # кратеры
    for _ in range(6):
        ang = rng.uniform(0, 2 * math.pi)
        d = rng.uniform(0, r * 0.7)
        cr = rng.uniform(r * 0.08, r * 0.2)
        c.fill_circle(cx + math.cos(ang) * d, cy + math.sin(ang) * d, cr,
                      _adjust(p.accent, 0.85), alpha=0.5, soft=1.0)


def draw_planet(c: Canvas, scene: Scene, rng: random.Random, horizon: int) -> None:
    p = scene.palette
    cx = c.width * rng.uniform(0.25, 0.75)
    cy = horizon * rng.uniform(0.3, 0.6)
    r = min(c.width, c.height) * rng.uniform(0.12, 0.18)
    base = scene.named_color or (200, 150, 110)
    c.fill_circle(cx, cy, r, base, soft=1.5)
    # полосы
    for i in range(-3, 4):
        band = _adjust(base, 1.0 + 0.1 * (i % 2))
        c.fill_circle(cx, cy + i * r * 0.28, r * 0.98, band, alpha=0.18, soft=1.0)
    # кольцо
    for t in range(240):
        ang = t / 240 * 2 * math.pi
        rx, ry = r * 1.8, r * 0.5
        x = cx + math.cos(ang) * rx
        y = cy + math.sin(ang) * ry
        if math.sin(ang) < 0 or (x - cx) ** 2 + (y - cy) ** 2 > r * r:
            c.fill_circle(x, y, 1.2, mix(base, p.detail, 0.5), alpha=0.7, soft=0.8)


def draw_clouds(c: Canvas, scene: Scene, rng: random.Random, horizon: int) -> None:
    p = scene.palette
    n = 3 * max(1, scene.count("clouds", 1))
    cloud = mix(p.sky_bottom, p.detail, 0.6) if p.name != "storm" else _adjust(p.sky_top, 1.3)
    for _ in range(n):
        cx = rng.uniform(0, c.width)
        cy = rng.uniform(horizon * 0.1, horizon * 0.55)
        scale = rng.uniform(0.6, 1.4)
        for _ in range(6):
            ox = rng.uniform(-30, 30) * scale
            oy = rng.uniform(-8, 8) * scale
            r = rng.uniform(10, 22) * scale
            c.fill_circle(cx + ox, cy + oy, r, cloud, alpha=0.55, soft=3.0)


def draw_rainbow(c: Canvas, scene: Scene, rng: random.Random, horizon: int) -> None:
    colors = [(228, 60, 60), (240, 150, 60), (245, 220, 90),
              (80, 190, 100), (70, 130, 220), (150, 90, 210)]
    cx = c.width * 0.5
    cy = horizon * 1.05
    base = c.width * 0.55
    for i, col in enumerate(colors):
        r = base - i * (c.width * 0.02)
        for t in range(200):
            ang = math.pi * t / 199
            x = cx + math.cos(ang) * r
            y = cy - math.sin(ang) * r
            c.fill_circle(x, y, c.width * 0.012, col, alpha=0.5, soft=1.5)


# ---------------------------------------------------------------------------
# Слои: рельеф и земля
# ---------------------------------------------------------------------------


def draw_mountains(c: Canvas, scene: Scene, rng: random.Random, horizon: int) -> None:
    p = scene.palette
    layers = 2 + max(1, scene.count("mountains", 1))
    for layer in range(layers):
        depth = layer / max(layers - 1, 1)
        col = mix(p.silhouette, p.sky_bottom, 0.5 - 0.4 * (1 - depth))
        col = _adjust(col, 0.7 + 0.3 * depth)
        base_y = horizon - (layers - layer) * (horizon * 0.04)
        peaks = rng.randint(3, 5)
        pts: List[Point] = [(0, horizon)]
        step = c.width / peaks
        for i in range(peaks + 1):
            x = i * step + rng.uniform(-step * 0.2, step * 0.2)
            peak_h = rng.uniform(0.18, 0.42) * horizon * (0.7 + 0.5 * (1 - depth))
            y = base_y - peak_h
            pts.append((x, y))
            pts.append((x + step * 0.5, base_y - peak_h * rng.uniform(0.3, 0.7)))
        pts.append((c.width, horizon))
        c.fill_polygon(pts, col)
        # снежные шапки для зимы/высоких гор
        if p.name == "winter" or layer == layers - 1:
            for i in range(1, len(pts) - 1, 2):
                x, y = pts[i]
                if y < base_y - horizon * 0.18:
                    c.fill_polygon([(x - 10, y + 14), (x, y), (x + 10, y + 14)],
                                   (240, 244, 250), alpha=0.9)


def draw_hills(c: Canvas, scene: Scene, rng: random.Random, horizon: int) -> None:
    p = scene.palette
    for layer in range(3):
        depth = layer / 2
        col = _adjust(p.ground, 0.7 + 0.3 * depth)
        base_y = horizon + layer * (c.height - horizon) * 0.12
        pts: List[Point] = [(0, c.height)]
        n = 6
        for i in range(n + 1):
            x = c.width * i / n
            y = base_y + math.sin(i * 1.7 + layer) * (c.height - horizon) * 0.06
            pts.append((x, y))
        pts.append((c.width, c.height))
        c.fill_polygon(pts, col)


def draw_ground(c: Canvas, scene: Scene, rng: random.Random, horizon: int) -> None:
    p = scene.palette
    ground = p.ground
    for y in range(horizon, c.height):
        t = (y - horizon) / max(c.height - horizon, 1)
        col = mix(ground, p.ground_shadow, t)
        c._buf[y] = list(col) * c.width


def draw_sea(c: Canvas, scene: Scene, rng: random.Random, horizon: int) -> None:
    p = scene.palette
    top = mix(p.sky_bottom, (30, 90, 150), 0.6)
    bottom = _adjust(top, 0.5)
    for y in range(horizon, c.height):
        t = (y - horizon) / max(c.height - horizon, 1)
        col = mix(top, bottom, t)
        c._buf[y] = list(col) * c.width
    # блики
    for _ in range(int(c.width * 1.2)):
        y = rng.randint(horizon, c.height - 1)
        x = rng.randint(0, c.width - 1)
        w = rng.uniform(2, 10)
        c.line(x, y, x + w, y, mix(col, p.accent, 0.6), width=1, alpha=0.25)


def draw_desert(c: Canvas, scene: Scene, rng: random.Random, horizon: int) -> None:
    sand_top = (222, 184, 120)
    sand_bottom = (176, 132, 78)
    for layer in range(3):
        col = mix(sand_top, sand_bottom, layer / 2)
        base_y = horizon + layer * (c.height - horizon) * 0.18
        pts: List[Point] = [(0, c.height)]
        for i in range(7):
            x = c.width * i / 6
            y = base_y + math.sin(i * 2.0 + layer * 1.3) * 12
            pts.append((x, y))
        pts.append((c.width, c.height))
        c.fill_polygon(pts, col)


# ---------------------------------------------------------------------------
# Объекты на земле
# ---------------------------------------------------------------------------


def draw_trees(c: Canvas, scene: Scene, rng: random.Random, horizon: int) -> None:
    p = scene.palette
    n = 6 * max(1, scene.count("trees", 2))
    leaf = _adjust(p.ground, 1.05)
    if p.name == "autumn":
        leaf = (196, 120, 50)
    if p.name == "winter":
        leaf = (60, 110, 80)
    trunk = (70, 50, 36)
    for _ in range(n):
        x = rng.uniform(0, c.width)
        depth = rng.uniform(0.0, 1.0)
        y = horizon + depth * (c.height - horizon) * 0.5
        size = (10 + depth * 22)
        # ёлка треугольником
        c.rect(int(x - size * 0.08), int(y), int(x + size * 0.08), int(y + size * 0.4), trunk)
        for k in range(3):
            top = y - size * (1.0 - k * 0.28)
            half = size * (0.28 + k * 0.16)
            base = y - size * (0.55 - k * 0.28)
            c.fill_polygon([(x - half, base), (x, top), (x + half, base)],
                           _adjust(leaf, 0.9 + 0.1 * depth))


def draw_flowers(c: Canvas, scene: Scene, rng: random.Random, horizon: int) -> None:
    n = 40 * max(1, scene.count("flower", 1))
    petals_colors = [(240, 90, 120), (250, 200, 80), (200, 120, 220), (240, 250, 250)]
    for _ in range(n):
        x = rng.uniform(0, c.width)
        y = rng.uniform(horizon, c.height)
        col = rng.choice(petals_colors)
        c.line(x, y, x, y + 6, (60, 140, 70), width=1)
        for k in range(5):
            ang = k / 5 * 2 * math.pi
            c.fill_circle(x + math.cos(ang) * 2.5, y + math.sin(ang) * 2.5, 1.8, col, soft=0.6)
        c.fill_circle(x, y, 1.6, (250, 220, 90), soft=0.6)


def draw_house(c: Canvas, scene: Scene, rng: random.Random, horizon: int) -> None:
    p = scene.palette
    n = max(1, scene.count("house", 1))
    for _ in range(n):
        w = rng.uniform(c.width * 0.1, c.width * 0.16)
        h = w * 0.8
        x = rng.uniform(c.width * 0.15, c.width * 0.85)
        y = horizon + (c.height - horizon) * rng.uniform(0.15, 0.4)
        wall = scene.named_color or (210, 190, 160)
        c.rect(int(x - w / 2), int(y - h), int(x + w / 2), int(y), wall)
        # крыша
        c.fill_polygon([(x - w / 2 - 4, y - h), (x, y - h - h * 0.5), (x + w / 2 + 4, y - h)],
                       (150, 70, 60))
        # окно
        win = mix(p.accent, (255, 240, 180), 0.5) if p.name in ("night", "sunset") else (120, 160, 190)
        c.rect(int(x - w * 0.12), int(y - h * 0.6), int(x + w * 0.12), int(y - h * 0.25), win)
        # дверь
        c.rect(int(x - w * 0.1), int(y - h * 0.4), int(x + w * 0.1), int(y), (90, 60, 44))


def draw_city(c: Canvas, scene: Scene, rng: random.Random, horizon: int) -> None:
    p = scene.palette
    x = 0
    while x < c.width:
        w = rng.uniform(c.width * 0.04, c.width * 0.09)
        h = rng.uniform(c.height * 0.12, c.height * 0.4)
        top = horizon - h
        base = _adjust(p.silhouette, rng.uniform(0.9, 1.4))
        if p.name == "neon":
            base = _adjust(mix(p.silhouette, p.detail, 0.15), 1.0)
        c.rect(int(x), int(top), int(x + w), horizon, base)
        # окна
        lit = p.accent if p.name in ("night", "sunset", "neon") else (150, 180, 200)
        for wy in range(int(top) + 4, horizon - 3, 6):
            for wx in range(int(x) + 3, int(x + w) - 2, 5):
                if rng.random() < 0.5:
                    c.rect(wx, wy, wx + 2, wy + 3, lit, alpha=0.85)
        x += w + rng.uniform(1, 4)


def draw_boat(c: Canvas, scene: Scene, rng: random.Random, horizon: int) -> None:
    p = scene.palette
    x = c.width * rng.uniform(0.3, 0.7)
    y = horizon + (c.height - horizon) * rng.uniform(0.1, 0.3)
    w = c.width * 0.08
    hull = (60, 45, 40)
    c.fill_polygon([(x - w, y), (x + w, y), (x + w * 0.6, y + w * 0.4), (x - w * 0.6, y + w * 0.4)], hull)
    # мачта и парус
    c.line(x, y, x, y - w * 1.6, (40, 30, 26), width=2)
    c.fill_polygon([(x, y - w * 1.5), (x, y - w * 0.2), (x + w * 0.9, y - w * 0.3)],
                   mix(p.detail, p.accent, 0.3))


def draw_bird(c: Canvas, scene: Scene, rng: random.Random, horizon: int) -> None:
    n = 5 * max(1, scene.count("bird", 1))
    col = _adjust(scene.palette.silhouette, 1.2)
    for _ in range(n):
        x = rng.uniform(c.width * 0.1, c.width * 0.9)
        y = rng.uniform(horizon * 0.15, horizon * 0.6)
        s = rng.uniform(3, 7)
        c.line(x - s, y + s * 0.4, x, y, col, width=1.4)
        c.line(x, y, x + s, y + s * 0.4, col, width=1.4)


# ---------------------------------------------------------------------------
# Погода поверх всего
# ---------------------------------------------------------------------------


def draw_rain(c: Canvas, scene: Scene, rng: random.Random, horizon: int) -> None:
    n = int(c.width * 2.5)
    for _ in range(n):
        x = rng.uniform(0, c.width)
        y = rng.uniform(0, c.height)
        L = rng.uniform(6, 12)
        c.line(x, y, x - 2, y + L, (200, 210, 230), width=1, alpha=0.35)


def draw_snow(c: Canvas, scene: Scene, rng: random.Random, horizon: int) -> None:
    n = int(c.width * 1.8)
    for _ in range(n):
        x = rng.uniform(0, c.width)
        y = rng.uniform(0, c.height)
        r = rng.uniform(0.8, 2.2)
        c.fill_circle(x, y, r, (250, 252, 255), alpha=0.85, soft=0.8)


def draw_fog(c: Canvas, scene: Scene, rng: random.Random, horizon: int) -> None:
    for _ in range(14):
        y = rng.uniform(horizon * 0.5, c.height)
        band = int(rng.uniform(6, 20))
        for yy in range(int(y), min(c.height, int(y) + band)):
            for x in range(c.width):
                i = x * 3
                row = c._buf[yy]
                row[i] = min(255, int(row[i] * 0.7 + 200 * 0.3))
                row[i + 1] = min(255, int(row[i + 1] * 0.7 + 205 * 0.3))
                row[i + 2] = min(255, int(row[i + 2] * 0.7 + 210 * 0.3))
