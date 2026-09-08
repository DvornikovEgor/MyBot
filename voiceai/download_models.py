"""Скачивание нейромодели Silero v4 (русские голоса) в каталог models/.

Источники пробуются по порядку:
  1. официальный сервер Silero (models.silero.ai);
  2. зеркало на GitHub (архив репозитория с моделью).

Запуск:  python -m voiceai.download_models
"""

from __future__ import annotations

import io
import os
import sys
import tarfile
import urllib.request
from typing import Callable, Optional

from .engines.silero import MODEL_FILE, MODELS_DIR

MODEL_SIZE_MB = 40

SOURCES = [
    ("официальный сервер Silero",
     "https://models.silero.ai/models/tts/ru/v4_ru.pt",
     "direct"),
    ("зеркало на GitHub (архив)",
     "https://codeload.github.com/daswer123/silero-tts-enhanced/tar.gz/refs/heads/main",
     "tarball"),
]

_USER_AGENT = {"User-Agent": "MyBot-VoiceAI/1.0 (+https://github.com/DvornikovEgor/MyBot)"}


class DownloadError(RuntimeError):
    pass


def _stream(url: str, on_progress: Optional[Callable[[int, int], None]] = None) -> bytes:
    req = urllib.request.Request(url, headers=_USER_AGENT)
    with urllib.request.urlopen(req, timeout=60) as resp:
        total = int(resp.headers.get("Content-Length") or 0)
        buf = io.BytesIO()
        done = 0
        while True:
            chunk = resp.read(1024 * 256)
            if not chunk:
                break
            buf.write(chunk)
            done += len(chunk)
            if on_progress:
                on_progress(done, total)
        return buf.getvalue()


def _extract_from_tarball(data: bytes) -> bytes:
    """Достаёт файл модели .pt из архива репозитория."""
    with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as tar:
        for member in tar.getmembers():
            if member.isfile() and member.name.endswith("v4_ru_ru.pt"):
                f = tar.extractfile(member)
                if f:
                    return f.read()
    raise DownloadError("В архиве не найден файл модели")


def download_model(
    dest: str = MODEL_FILE,
    on_progress: Optional[Callable[[str, int, int], None]] = None,
) -> str:
    """Скачивает модель и кладёт её в ``dest``. Возвращает путь к файлу."""
    os.makedirs(os.path.dirname(dest), exist_ok=True)

    if os.path.isfile(dest) and os.path.getsize(dest) > MODEL_SIZE_MB * 1024 * 1024 // 2:
        return dest

    last_error = ""
    for title, url, kind in SOURCES:
        try:
            def progress(done: int, total: int) -> None:
                if on_progress:
                    on_progress(title, done, total)

            data = _stream(url, progress)
            if kind == "tarball":
                data = _extract_from_tarball(data)
            if len(data) < 10 * 1024 * 1024:
                raise DownloadError(f"подозрительно маленький файл ({len(data)} байт)")
            tmp = dest + ".part"
            with open(tmp, "wb") as fh:
                fh.write(data)
            os.replace(tmp, dest)
            return dest
        except Exception as exc:  # пробуем следующий источник
            last_error = f"{title}: {exc}"
            continue

    raise DownloadError(
        "Не удалось скачать модель ни из одного источника. "
        "Проверьте интернет и повторите. Последняя ошибка: " + last_error
    )


def main() -> int:
    def show(title: str, done: int, total: int) -> None:
        if total:
            sys.stdout.write(f"\r[{title}] {done // 1048576} МБ из {total // 1048576} МБ")
        else:
            sys.stdout.write(f"\r[{title}] {done // 1048576} МБ")
        sys.stdout.flush()

    try:
        path = download_model(on_progress=show)
    except DownloadError as exc:
        print(f"\nОшибка: {exc}", file=sys.stderr)
        return 1
    print(f"\nМодель готова: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
