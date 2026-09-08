"""Кодировщик PNG на чистом Python.

Использует только стандартную библиотеку (``zlib`` и ``struct``), никаких
Pillow и прочих зависимостей. Пишет 8-битные RGB-изображения.
"""

from __future__ import annotations

import struct
import zlib
from typing import List, Sequence

__all__ = ["write_png", "encode_png"]


def _chunk(tag: bytes, data: bytes) -> bytes:
    """Собрать один chunk PNG: длина, тег, данные, CRC32."""
    return (
        struct.pack(">I", len(data))
        + tag
        + data
        + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
    )


def encode_png(pixels: Sequence[Sequence[int]], width: int, height: int) -> bytes:
    """Закодировать плоский список RGB-байтов в PNG.

    ``pixels`` — это список строк, каждая строка — список байтов
    ``[r, g, b, r, g, b, ...]`` длиной ``width * 3``.
    """
    signature = b"\x89PNG\r\n\x1a\n"

    # IHDR: ширина, высота, глубина 8 бит, цветовой тип 2 (truecolor RGB)
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)

    # каждая строка предваряется байтом фильтра (0 = без фильтра)
    raw = bytearray()
    for row in pixels:
        raw.append(0)
        raw.extend(row)

    idat = zlib.compress(bytes(raw), 9)

    return (
        signature
        + _chunk(b"IHDR", ihdr)
        + _chunk(b"IDAT", idat)
        + _chunk(b"IEND", b"")
    )


def write_png(path: str, pixels: Sequence[Sequence[int]], width: int, height: int) -> None:
    """Записать PNG-файл на диск."""
    with open(path, "wb") as f:
        f.write(encode_png(pixels, width, height))
