"""Клонирование голоса на базе XTTS v2 (Coqui).

Пользователь загружает короткую запись голоса (6–30 секунд), а нейросеть
озвучивает любой текст этим голосом. Поддерживается 17 языков, включая
русский.

Модель весит ~1.9 ГБ и скачивается отдельно (см. ``download_model`` /
кнопку в веб-интерфейсе). До скачивания движок помечается как
``needs_model`` и приложение продолжает работать остальными движками.
"""

from __future__ import annotations

import json
import os
import threading
import urllib.request
from typing import Callable, Dict, List, Optional

from .base import Engine, EngineError, SynthResult, Voice

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
MODEL_DIR = os.path.join(BASE_DIR, "models", "xtts-v2")
SAMPLES_DIR = os.path.join(BASE_DIR, "voice_samples")

HF_REPO = "coqui/XTTS-v2"
MODEL_FILES = ["config.json", "vocab.json", "hash", "speakers_xtts.pth", "model.pth"]
MODEL_TOTAL_MB = 1900

# Языки, которые понимает XTTS v2 (код → подпись для интерфейса)
LANGUAGES = {
    "ru": "Русский",
    "en": "Английский",
    "de": "Немецкий",
    "fr": "Французский",
    "es": "Испанский",
    "it": "Итальянский",
    "pl": "Польский",
    "tr": "Турецкий",
    "pt": "Португальский",
    "nl": "Нидерландский",
    "cs": "Чешский",
    "ar": "Арабский",
    "zh-cn": "Китайский",
    "ja": "Японский",
    "ko": "Корейский",
    "hi": "Хинди",
    "hu": "Венгерский",
}


class XTTSEngine(Engine):
    id = "xtts"
    title = "Клонирование голоса (XTTS v2)"
    kind = "clone"

    def __init__(self) -> None:
        super().__init__()
        self._model = None
        self._lock = threading.Lock()

        try:
            import TTS  # noqa: F401
            deps_ok = True
        except Exception as exc:  # pragma: no cover
            deps_ok = False
            self.why_not = f"Библиотека TTS не установлена: {exc}"

        if deps_ok and not self.model_ready():
            self.needs_model = True
            self.why_not = (
                "Модель XTTS v2 (~1.9 ГБ) ещё не скачана. "
                "Нажмите «Скачать модель» в интерфейсе."
            )
        elif deps_ok:
            self.available = True

    # ------------------------------------------------------------------ #

    def model_ready(self) -> bool:
        """Проверяет, что все файлы модели на месте."""
        if not os.path.isdir(MODEL_DIR):
            return False
        return all(
            os.path.isfile(os.path.join(MODEL_DIR, name)) for name in MODEL_FILES
        )

    def _ensure_model(self):
        if self._model is not None:
            return self._model
        with self._lock:
            if self._model is not None:
                return self._model
            if not self.model_ready():
                raise EngineError(
                    "Модель XTTS v2 не найдена. Скачайте её кнопкой в интерфейсе "
                    "или командой: python -m voiceai.download_clone_model"
                )
            try:
                import torch
                from TTS.api import TTS as CoquiTTS

                torch.set_num_threads(max(1, min(4, os.cpu_count() or 1)))
                model = CoquiTTS(model_path=MODEL_DIR)
            except Exception as exc:
                raise EngineError(f"Не удалось загрузить модель клонирования: {exc}") from exc
            self._model = model
            return model

    def warmup(self) -> None:
        if self.available:
            self._ensure_model()

    # ------------------------------------------------------------------ #
    #  Библиотека образцов голоса                                          #
    # ------------------------------------------------------------------ #

    def list_samples(self) -> List[Dict]:
        result = []
        if not os.path.isdir(SAMPLES_DIR):
            return result
        for slug in sorted(os.listdir(SAMPLES_DIR)):
            meta_path = os.path.join(SAMPLES_DIR, slug, "meta.json")
            wav_path = os.path.join(SAMPLES_DIR, slug, "sample.wav")
            if not (os.path.isfile(meta_path) and os.path.isfile(wav_path)):
                continue
            try:
                with open(meta_path, encoding="utf-8") as fh:
                    meta = json.load(fh)
                meta["slug"] = slug
                meta["url"] = f"/samples/{slug}"
                result.append(meta)
            except Exception:
                continue
        return result

    def sample_path(self, slug: str) -> str:
        return os.path.join(SAMPLES_DIR, slug, "sample.wav")

    # ------------------------------------------------------------------ #

    def voices(self) -> List[Voice]:
        """«Голоса» клонирования — это сохранённые образцы пользователя."""
        return [
            Voice(
                id=s["slug"],
                name=s.get("name", s["slug"]),
                gender="клон",
                lang="ru",
                description="Голос, созданный из вашей записи",
            )
            for s in self.list_samples()
        ]

    def synthesize(
        self,
        text: str,
        voice_id: str,
        *,
        speed: float = 1.0,
        sample_rate: int = 24000,
        options: Optional[Dict] = None,
    ) -> SynthResult:
        options = options or {}
        language = options.get("language", "ru")
        if language not in LANGUAGES:
            raise EngineError(f"Неизвестный язык «{language}»")

        wav_path = self.sample_path(voice_id)
        if not os.path.isfile(wav_path):
            raise EngineError("Образец голоса не найден — загрузите запись заново")

        model = self._ensure_model()
        with self._lock:
            try:
                out_path = os.path.join(SAMPLES_DIR, ".last_clone.wav")
                model.tts_to_file(
                    text=text,
                    speaker_wav=wav_path,
                    language=language,
                    file_path=out_path,
                    speed=max(0.5, min(2.0, float(speed))),
                )
                with open(out_path, "rb") as fh:
                    audio = fh.read()
            except EngineError:
                raise
            except Exception as exc:
                raise EngineError(f"Не удалось склонировать голос: {exc}") from exc

        return SynthResult(audio=audio, content_type="audio/wav",
                           sample_rate=24000, ext="wav")

    # ------------------------------------------------------------------ #
    #  Скачивание модели                                                   #
    # ------------------------------------------------------------------ #

    def download_model(
        self,
        on_progress: Optional[Callable[[int, int, str], None]] = None,
    ) -> str:
        """Качает файлы модели с Hugging Face в ``MODEL_DIR`` (с докачкой)."""
        os.makedirs(MODEL_DIR, exist_ok=True)

        for name in MODEL_FILES:
            dest = os.path.join(MODEL_DIR, name)
            if os.path.isfile(dest) and os.path.getsize(dest) > 0:
                if on_progress:
                    on_progress(-1, -1, f"{name}: уже на месте")
                continue

            url = f"https://huggingface.co/{HF_REPO}/resolve/main/{name}"
            tmp = dest + ".part"
            done = os.path.getsize(tmp) if os.path.isfile(tmp) else 0
            headers = {"User-Agent": "MyBot-VoiceAI/1.0"}
            if done:
                headers["Range"] = f"bytes={done}-"

            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=120) as resp:
                total = int(resp.headers.get("Content-Length") or 0) + done
                mode = "ab" if done else "wb"
                with open(tmp, mode) as fh:
                    while True:
                        chunk = resp.read(1024 * 512)
                        if not chunk:
                            break
                        fh.write(chunk)
                        done += len(chunk)
                        if on_progress:
                            on_progress(done, total, name)
            os.replace(tmp, dest)

        return MODEL_DIR
