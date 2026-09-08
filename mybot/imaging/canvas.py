"""Растровый холст: пиксели, фигуры, градиенты, альфа-смешивание, шрифт.

Всё на чистом Python. Цвета — кортежи (r, g, b) в диапазоне 0..255.
Координаты — с плавающей точкой, где это удобно; начало в левом верхнем углу.
"""

from __future__ import annotations

import math
from typing import List, Optional, Sequence, Tuple

from .png import write_png

Color = Tuple[int, int, int]

__all__ = ["Canvas", "Color"]


def _clamp8(v: float) -> int:
    if v < 0:
        return 0
    if v > 255:
        return 255
    return int(v + 0.5)


def lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def mix(c1: Color, c2: Color, t: float) -> Color:
    """Линейно смешать два цвета (t=0 -> c1, t=1 -> c2)."""
    return (
        _clamp8(lerp(c1[0], c2[0], t)),
        _clamp8(lerp(c1[1], c2[1], t)),
        _clamp8(lerp(c1[2], c2[2], t)),
    )


class Canvas:
    """Простой RGB-холст с базовым рисованием и сглаживанием краёв."""

    def __init__(self, width: int, height: int, background: Color = (0, 0, 0)):
        self.width = int(width)
        self.height = int(height)
        # буфер как список списков [r,g,b,r,g,b,...] по строкам
        r, g, b = background
        self._buf: List[List[int]] = [
            [r, g, b] * self.width for _ in range(self.height)
        ]

    # --- доступ к пикселям --------------------------------------------------

    def set_pixel(self, x: int, y: int, color: Color, alpha: float = 1.0) -> None:
        if x < 0 or x >= self.width or y < 0 or y >= self.height:
            return
        if alpha <= 0.0:
            return
        row = self._buf[y]
        i = x * 3
        if alpha >= 1.0:
            row[i], row[i + 1], row[i + 2] = color
        else:
            row[i] = _clamp8(lerp(row[i], color[0], alpha))
            row[i + 1] = _clamp8(lerp(row[i + 1], color[1], alpha))
            row[i + 2] = _clamp8(lerp(row[i + 2], color[2], alpha))

    def get_pixel(self, x: int, y: int) -> Color:
        row = self._buf[y]
        i = x * 3
        return (row[i], row[i + 1], row[i + 2])

    # --- заливки ------------------------------------------------------------

    def fill(self, color: Color) -> None:
        r, g, b = color
        for y in range(self.height):
            self._buf[y] = [r, g, b] * self.width

    def vertical_gradient(self, top: Color, bottom: Color) -> None:
        """Вертикальный градиент от top (сверху) к bottom (снизу)."""
        h = max(self.height - 1, 1)
        for y in range(self.height):
            t = y / h
            c = mix(top, bottom, t)
            self._buf[y] = list(c) * self.width

    def gradient(self, top: Color, bottom: Color) -> None:
        self.vertical_gradient(top, bottom)

    # --- примитивы ----------------------------------------------------------

    def rect(self, x0: int, y0: int, x1: int, y1: int, color: Color,
             alpha: float = 1.0) -> None:
        for y in range(max(0, y0), min(self.height, y1)):
            for x in range(max(0, x0), min(self.width, x1)):
                self.set_pixel(x, y, color, alpha)

    def fill_circle(self, cx: float, cy: float, radius: float, color: Color,
                    alpha: float = 1.0, soft: float = 1.0) -> None:
        """Круг со сглаженной кромкой шириной ``soft`` пикселей."""
        x0 = int(math.floor(cx - radius - soft))
        x1 = int(math.ceil(cx + radius + soft))
        y0 = int(math.floor(cy - radius - soft))
        y1 = int(math.ceil(cy + radius + soft))
        for y in range(max(0, y0), min(self.height, y1 + 1)):
            for x in range(max(0, x0), min(self.width, x1 + 1)):
                d = math.hypot(x + 0.5 - cx, y + 0.5 - cy)
                edge = radius - d
                if edge >= soft:
                    a = alpha
                elif edge <= -soft:
                    continue
                else:
                    a = alpha * (edge + soft) / (2 * soft)
                self.set_pixel(x, y, color, a)

    def ring(self, cx: float, cy: float, radius: float, thickness: float,
             color: Color, alpha: float = 1.0) -> None:
        inner = radius - thickness
        x0 = int(math.floor(cx - radius - 1))
        x1 = int(math.ceil(cx + radius + 1))
        y0 = int(math.floor(cy - radius - 1))
        y1 = int(math.ceil(cy + radius + 1))
        for y in range(max(0, y0), min(self.height, y1 + 1)):
            for x in range(max(0, x0), min(self.width, x1 + 1)):
                d = math.hypot(x + 0.5 - cx, y + 0.5 - cy)
                if inner - 1 <= d <= radius + 1:
                    a = alpha
                    if d > radius:
                        a *= max(0.0, 1.0 - (d - radius))
                    elif d < inner:
                        a *= max(0.0, 1.0 - (inner - d))
                    self.set_pixel(x, y, color, a)

    def line(self, x0: float, y0: float, x1: float, y1: float, color: Color,
             width: float = 1.0, alpha: float = 1.0) -> None:
        """Отрезок толщиной width (рисуется как цепочка кружков)."""
        dist = math.hypot(x1 - x0, y1 - y0)
        steps = max(1, int(dist))
        r = width / 2.0
        for i in range(steps + 1):
            t = i / steps
            self.fill_circle(lerp(x0, x1, t), lerp(y0, y1, t), r, color, alpha, soft=0.8)

    def fill_polygon(self, points: Sequence[Tuple[float, float]], color: Color,
                     alpha: float = 1.0) -> None:
        """Заливка выпуклого/невыпуклого многоугольника (scanline)."""
        if len(points) < 3:
            return
        ys = [p[1] for p in points]
        y_min = max(0, int(math.floor(min(ys))))
        y_max = min(self.height - 1, int(math.ceil(max(ys))))
        n = len(points)
        for y in range(y_min, y_max + 1):
            yc = y + 0.5
            nodes = []
            j = n - 1
            for i in range(n):
                yi, yj = points[i][1], points[j][1]
                if (yi < yc <= yj) or (yj < yc <= yi):
                    xi, xj = points[i][0], points[j][0]
                    nodes.append(xi + (yc - yi) / (yj - yi) * (xj - xi))
                j = i
            nodes.sort()
            for k in range(0, len(nodes) - 1, 2):
                xa = int(math.ceil(nodes[k] - 0.5))
                xb = int(math.floor(nodes[k + 1] - 0.5))
                for x in range(max(0, xa), min(self.width - 1, xb) + 1):
                    self.set_pixel(x, y, color, alpha)

    def star(self, cx: float, cy: float, outer: float, inner: float, points: int,
             color: Color, rotation: float = -math.pi / 2, alpha: float = 1.0) -> None:
        verts = []
        for i in range(points * 2):
            r = outer if i % 2 == 0 else inner
            ang = rotation + i * math.pi / points
            verts.append((cx + r * math.cos(ang), cy + r * math.sin(ang)))
        self.fill_polygon(verts, color, alpha)

    # --- пост-обработка -----------------------------------------------------

    def add_noise(self, amount: int, rng) -> None:
        """Добавить лёгкое зерно (для «плёночного» эффекта)."""
        if amount <= 0:
            return
        for y in range(self.height):
            row = self._buf[y]
            for i in range(len(row)):
                row[i] = _clamp8(row[i] + rng.randint(-amount, amount))

    def vignette(self, strength: float = 0.35) -> None:
        """Затемнить углы (виньетка)."""
        cx, cy = self.width / 2.0, self.height / 2.0
        maxd = math.hypot(cx, cy)
        for y in range(self.height):
            row = self._buf[y]
            for x in range(self.width):
                d = math.hypot(x - cx, y - cy) / maxd
                f = 1.0 - strength * (d ** 2)
                i = x * 3
                row[i] = _clamp8(row[i] * f)
                row[i + 1] = _clamp8(row[i + 1] * f)
                row[i + 2] = _clamp8(row[i + 2] * f)

    # --- сохранение ---------------------------------------------------------

    def save(self, path: str) -> None:
        write_png(path, self._buf, self.width, self.height)

    def to_png_bytes(self) -> bytes:
        from .png import encode_png
        return encode_png(self._buf, self.width, self.height)
