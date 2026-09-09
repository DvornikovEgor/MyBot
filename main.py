#!/usr/bin/env python3
"""Точка входа: интерактивный чат с ботом прямо в терминале.

Запуск:  python3 main.py
Тесты:   python3 -m unittest discover tests -v
"""

from bot import Brain

BANNER = """\
==========================================================
  MyBot — локальный ИИ на чистом Python
  Без API, без интернета, без сторонних библиотек.
  Наберите /помощь — список команд, /выход — выход.
==========================================================
"""

EXIT_WORDS = {"/выход", "/выход!", "/вывход", "/выход.", "выход", "выйти", "/выход,"}


def run_chat(brain=None):
    print(BANNER)
    brain = brain or Brain()
    name = brain.profile.get("name")
    greeting = f"С возвращением, {name}!" if name else "Чем могу помочь?"
    print(f"Бот> {greeting}")

    while True:
        try:
            user = input("Вы> ")
        except (EOFError, KeyboardInterrupt):
            print("\nБот> До встречи! 👋")
            break

        user = user.strip()
        if not user:
            continue
        if user.lower() in EXIT_WORDS:
            print("Бот> До встречи! 👋")
            break

        answer = brain.reply(user)
        brain.replies_given += 1
        print(f"Бот> {answer}")


if __name__ == "__main__":
    run_chat()
