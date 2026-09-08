"""Точка входа: `python -m mybot` показывает список демо."""

import sys

DEMOS = {
    "xor": "mybot.apps.xor",
    "spiral": "mybot.apps.spiral",
    "textgen": "mybot.apps.textgen",
}

HELP = """MyBot — нейросети на чистом Python.

Использование:
  python -m mybot xor        обучить сеть логике XOR
  python -m mybot spiral     классификация двух спиралей + карта решений
  python -m mybot textgen    символьная RNN: обучение и генерация текста
  python -m mybot textgen --load --chat    поболтать с обученной моделью

Дополнительные флаги у каждого демо: добавьте --help, например
  python -m mybot textgen --help
"""


def main() -> None:
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help", "help"):
        print(HELP)
        return
    name = sys.argv[1]
    if name not in DEMOS:
        print("неизвестное демо: %s\n" % name)
        print(HELP)
        sys.exit(1)
    import importlib
    module = importlib.import_module(DEMOS[name])
    sys.argv = [sys.argv[0]] + sys.argv[2:]
    module.cli()


if __name__ == "__main__":
    main()
