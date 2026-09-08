"""Скачивание модели клонирования голоса XTTS v2 (~1.9 ГБ).

Запуск:  python -m voiceai.download_clone_model
"""

from __future__ import annotations

import sys

from .engines.xtts import XTTSEngine


def main() -> int:
    engine = XTTSEngine()

    def progress(done: int, total: int, name: str) -> None:
        if done < 0:
            sys.stdout.write(f"\r{name}                    ")
        elif total:
            sys.stdout.write(f"\r[{name}] {done // 1048576} МБ из {total // 1048576} МБ ({done * 100 // total}%)")
        else:
            sys.stdout.write(f"\r[{name}] {done // 1048576} МБ")
        sys.stdout.flush()

    try:
        path = engine.download_model(on_progress=progress)
    except Exception as exc:
        print(f"\nОшибка: {exc}", file=sys.stderr)
        print("Нужен доступ к huggingface.co. Повторите позже или скачайте вручную.", file=sys.stderr)
        return 1
    print(f"\nМодель готова: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
