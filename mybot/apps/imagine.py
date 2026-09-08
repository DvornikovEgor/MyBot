"""Демо 4: генерация картинки из текста (text-to-image) на чистом Python.

Запуск::

    python -m mybot imagine "закат над горами и море, лодка"
    python -m mybot imagine "звёздная ночь, луна и лес" -o night.png --size 768
    python -m mybot imagine "неоновый город, киберпанк" --no-caption

Движок разбирает промпт (ru/en), понимает время суток, погоду, объекты и стиль,
и рисует настоящий PNG — без нейросетей-гигантов, API и зависимостей.
"""

from __future__ import annotations

import argparse
import sys

from ..imaging.generator import generate
from ..imaging.prompt import OBJECT_WORDS


def cli() -> None:
    parser = argparse.ArgumentParser(
        description="MyBot: картинка из текста (offline, без зависимостей)")
    parser.add_argument("prompt", nargs="+", help="текстовое описание картинки")
    parser.add_argument("-o", "--out", default="output.png", help="куда сохранить PNG")
    parser.add_argument("--size", type=int, default=512, help="сторона квадрата, если не задано --width/--height")
    parser.add_argument("--width", type=int, default=None)
    parser.add_argument("--height", type=int, default=None)
    parser.add_argument("--seed", type=int, default=None, help="сид (по умолчанию из текста)")
    parser.add_argument("--no-caption", action="store_true", help="без подписи внизу")
    args = parser.parse_args()

    prompt = " ".join(args.prompt)
    width = args.width or args.size
    height = args.height or args.size

    scene = generate(prompt, args.out, width=width, height=height,
                     seed=args.seed, caption=not args.no_caption)

    print("промпт : %s" % prompt)
    print("палитра: %s" % scene.palette.name)
    print("объекты: %s" % (", ".join(scene.objects) if scene.objects else "— (только фон)"))
    print("стиль  : %s" % scene.style)
    print("сид    : %d" % scene.seed)
    print("файл   : %s (%dx%d)" % (args.out, width, height))
    if not scene.objects:
        known = ", ".join(sorted(OBJECT_WORDS))
        print("\nсовет: добавьте объекты в промпт. Движок знает: %s" % known)


if __name__ == "__main__":
    cli()
