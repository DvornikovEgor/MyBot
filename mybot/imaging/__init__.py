"""Генерация картинок из текста на чистом Python (без зависимостей).

Пример::

    from mybot.imaging import generate
    generate("закат над горами и море", "sunset.png")
"""

from .canvas import Canvas
from .generator import TextToImage, generate, render_scene
from .prompt import Scene, parse

__all__ = ["Canvas", "TextToImage", "generate", "render_scene", "Scene", "parse"]
