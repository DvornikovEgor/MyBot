"""
Предобработка пользовательских картинок к формату модели.

Модель обучена на рукописных цифрах (8×8 для `digits`, 28×28 для `mnist`).
Оригинальный датасет создавался так: цифру рисовали в квадрате 32×32, затем
усредняли блоками 4×4 → 8×8. Мы воспроизводим тот же путь:

  1) определяем полярность (тёмная цифра на светлом фоне или наоборот);
  2) вырезаем цифру по «чернилам» и центрируем её в квадрате;
  3) уменьшаем до размера side*4 (билинейно, со сглаживанием);
  4) усредняем блоками 4×4 до side×side — как в обучающих данных.
"""
from __future__ import annotations

from io import BytesIO

import numpy as np
from PIL import Image, ImageFilter

BORDER = 4  # во сколько раз промежуточный кадр больше целевого (side * BORDER)


# --------------------------------------------------------------------------- #
#  Вход: data-URL / PIL-изображение
# --------------------------------------------------------------------------- #
def from_data_url(data_url: str, side: int = 8) -> np.ndarray:
    """PNG/JPEG из data-URL → массив [1, side*side] в [0,1]."""
    import base64

    assert "," in data_url, "ожидался data:image/...;base64,..."
    raw = base64.b64decode(data_url.split(",", 1)[1])
    img = Image.open(BytesIO(raw))
    return from_image(img, side=side)


def from_image(img: Image.Image, side: int = 8, margin: float = 0.22) -> np.ndarray:
    """PIL-изображение → [1, side*side] float в [0,1]."""
    if img.mode != "L":
        img = img.convert("L")
    raw = np.asarray(img, dtype=np.float32) / 255.0
    a = to_ink(raw)
    a = _crop_to_ink(a, margin=margin)
    return _downsample_like_dataset(a, side).reshape(1, side * side)


def to_ink(raw: np.ndarray) -> np.ndarray:
    """Приводит картинку к виду «чернила», где 0 — фон, 1 — самая жирная точка."""
    border = np.concatenate([raw[0], raw[-1], raw[:, 0], raw[:, -1]])
    bg = float(np.median(border))          # фон: тёмный у холста, светлый у фото
    a = np.abs(raw - bg)
    peak = float(a.max())
    if peak > 0:
        a /= peak
    return a


# --------------------------------------------------------------------------- #
#  Геометрия и уменьшение
# --------------------------------------------------------------------------- #
def _crop_to_ink(a: np.ndarray, margin: float = 0.22,
                 size: int | None = None) -> np.ndarray:
    """Обрезает пустые поля и центрирует цифру в квадратном кадре."""
    H, W = a.shape
    ink = a > a.max() * 0.12 if a.max() > 0 else a > 0
    rows, cols = np.any(ink, axis=1), np.any(ink, axis=0)
    if size is None:
        size = TARGET_DEFAULT * BORDER
    if not rows.any():
        return np.zeros((size, size), dtype=np.float32)
    r0, r1 = np.flatnonzero(rows)[[0, -1]]
    c0, c1 = np.flatnonzero(cols)[[0, -1]]
    half = int(max(r1 - r0 + 1, c1 - c0 + 1) * (1.0 + margin) / 2.0) + 1
    cy, cx = (r0 + r1) // 2, (c0 + c1) // 2
    canvas = np.zeros((2 * half, 2 * half), dtype=np.float32)
    y0, x0 = max(0, cy - half), max(0, cx - half)
    y1, x1 = min(H, cy + half), min(W, cx + half)
    if y1 > y0 and x1 > x0:
        dy0, dx0 = y0 - (cy - half), x0 - (cx - half)
        canvas[dy0:dy0 + (y1 - y0), dx0:dx0 + (x1 - x0)] = a[y0:y1, x0:x1]
    return canvas


def _downsample_like_dataset(a: np.ndarray, side: int) -> np.ndarray:
    """size×size → side×side: билинейно до side*BORDER, затем блоками BORDER×BORDER."""
    big = side * BORDER
    im = Image.fromarray((np.clip(a, 0.0, 1.0) * 255).astype(np.uint8))
    im = im.resize((big, big), Image.Resampling.BILINEAR)
    if side > 1:  # лёгкое размытие, как в оригинальном датасете
        im = im.filter(ImageFilter.GaussianBlur(0.6))
    abig = np.asarray(im, dtype=np.float32) / 255.0
    return abig.reshape(side, BORDER, side, BORDER).mean(axis=(1, 3))


TARGET_DEFAULT = 8


# --------------------------------------------------------------------------- #
#  Аугментация: симуляция «нарисованных человеком» вариантов
# --------------------------------------------------------------------------- #
def random_affine(a: np.ndarray, rng: np.random.Generator,
                  scale_range=(0.55, 1.05), rot_deg=15.0,
                  shift_frac=0.08, brightness=(0.85, 1.15)) -> np.ndarray:
    """Случайный аффинный поворот/масштаб/сдвиг + лёгкая смена «жирности» штриха.

    Работает на увеличенном в 4 раза кадре, чтобы поворот был гладким.
    """
    from PIL import Image as PILImage

    H, W = a.shape
    up = 4
    im = PILImage.fromarray((np.clip(a, 0, 1) * 255).astype(np.uint8))
    im = im.resize((W * up, H * up), PILImage.Resampling.BILINEAR)
    U, V = W * up, H * up
    cx, cy = U / 2, V / 2

    s = rng.uniform(*scale_range)
    theta = np.deg2rad(rng.uniform(-rot_deg, rot_deg))
    tx, ty = rng.uniform(-shift_frac, shift_frac, size=2) * U
    cos_t, sin_t = np.cos(theta), np.sin(theta)

    # матрица выход→вход для PIL Image.transform(AFFINE)
    a11, a12 = cos_t / s, sin_t / s
    a21, a22 = -sin_t / s, cos_t / s
    c = cx - (a11 * (cx + tx) + a12 * (cy + ty))
    f = cy - (a21 * (cx + tx) + a22 * (cy + ty))

    im = im.transform((U, V), PILImage.Transform.AFFINE,
                      (a11, a12, c, a21, a22, f),
                      resample=PILImage.Resampling.BILINEAR)
    out = np.asarray(im, dtype=np.float32) / 255.0
    out = out * rng.uniform(*brightness)
    return np.clip(out, 0.0, 1.0)


def simulate_drawing(x: np.ndarray, side: int, rng: np.random.Generator,
                     margin: float = 0.22) -> np.ndarray:
    """Превращает «эталонную» картинку side×side в то, что модель увидит,
    если её нарисует человек: аффинные искажения + полный препроцессинг."""
    a8 = x.reshape(side, side)
    canvas = random_affine(a8, rng)
    canvas = _crop_to_ink(canvas, margin=margin, size=side * BORDER)
    return _downsample_like_dataset(canvas, side).reshape(-1)


def augment_dataset(x: np.ndarray, y: np.ndarray, side: int, copies: int = 6,
                    seed: int = 0) -> tuple[np.ndarray, np.ndarray]:
    """Добавляет к обучающей выборке copies «нарисованных» копий каждого примера."""
    rng = np.random.default_rng(seed)
    xs, ys = [x], [y]
    for _ in range(copies):
        aug = np.stack([simulate_drawing(xi, side, rng) for xi in x])
        xs.append(aug)
        ys.append(y)
    X = np.concatenate(xs)
    Y = np.concatenate(ys)
    perm = rng.permutation(len(X))
    return X[perm], Y[perm]


# --------------------------------------------------------------------------- #
#  Визуализация
# --------------------------------------------------------------------------- #
def to_ascii(a: np.ndarray, width: int = 16) -> str:
    """Маленькая ASCII-визуализация вектора/картинки для консоли."""
    if a.ndim == 1:
        side = int(round(a.size ** 0.5))
        a = a.reshape(side, side)
    im = Image.fromarray((np.clip(a, 0, 1) * 255).astype(np.uint8))
    im = im.resize((width, width), Image.Resampling.LANCZOS)
    vals = np.asarray(im, dtype=np.float32) / 255.0
    chars = " .:-=+*#%@"
    idx = (vals * (len(chars) - 1)).astype(int)
    return "\n".join("".join(chars[v] for v in row) for row in idx)
