"""Движок на базе нейросети Silero TTS v4 (русские голоса, полностью офлайн).

Модель распространяется свободно (см. лицензию проекта Silero) и весит ~40 МБ.
Файл модели ищется в каталоге ``models/`` рядом с корнем проекта; при
отсутствии его можно скачать командой ``python -m voiceai.download_models``
или кнопкой в веб-интерфейсе.
"""

from __future__ import annotations

import os
import threading
from typing import Dict, List, Optional
from xml.sax.saxutils import escape

from ..audio import numpy_to_wav
from .base import Engine, EngineError, SynthResult, Voice

MODELS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "models")
MODEL_FILE = os.path.join(MODELS_DIR, "v4_ru.pt")

PREVIEW_TEXT = "Привет! Меня зовут {name}. Я умею озвучивать любой текст."

SPEAKERS: Dict[str, Voice] = {
    "aidar": Voice(
        "aidar", "Айдар", "мужской", "ru",
        "Спокойный низкий мужской голос", PREVIEW_TEXT.format(name="Айдар"),
    ),
    "baya": Voice(
        "baya", "Бая", "женский", "ru",
        "Мягкий, по-детски лёгкий женский голос", PREVIEW_TEXT.format(name="Бая"),
    ),
    "kseniya": Voice(
        "kseniya", "Ксения", "женский", "ru",
        "Нейтральный женский голос, хорош для дикции", PREVIEW_TEXT.format(name="Ксения"),
    ),
    "xenia": Voice(
        "xenia", "Ксения‑2", "женский", "ru",
        "Второй женский тембр, чуть ниже", PREVIEW_TEXT.format(name="Ксения"),
    ),
    "eugene": Voice(
        "eugene", "Евгений", "мужской", "ru",
        "Энергичный мужской голос", PREVIEW_TEXT.format(name="Евгений"),
    ),
    "random": Voice(
        "random", "Случайный", "—", "ru",
        "Новый тембр при каждой генерации (эксперименты)",
        "Привет! Каждый раз я звучу немного по-разному.",
    ),
}

SAMPLE_RATES = (24000, 48000)


def _ssml_with_rate(text: str, speed: float) -> str:
    """Оборачивает текст в SSML с нужным темпом (модель понимает проценты)."""
    pct = int(round(max(0.25, min(2.0, speed)) * 100))
    return f'<speak><prosody rate="{pct}%">{escape(text)}</prosody></speak>'


class SileroEngine(Engine):
    id = "silero"
    title = "Нейросеть Silero (офлайн)"
    kind = "offline"

    def __init__(self) -> None:
        super().__init__()
        self._model = None
        self._lock = threading.Lock()
        self._init_error = ""

        try:
            import torch  # noqa: F401
            torch_ok = True
        except Exception as exc:  # pragma: no cover
            self._init_error = f"не установлен torch: {exc}"
            torch_ok = False

        if not torch_ok:
            self.available = False
            self.why_not = "Библиотека torch не установлена. Выполните: pip install torch"
        elif not os.path.isfile(MODEL_FILE):
            self.needs_model = True
            self.why_not = (
                "Файл нейромодели не найден (ожидается models/v4_ru.pt). "
                "Нажмите «Скачать модель» в интерфейсе или выполните "
                "python -m voiceai.download_models"
            )
        else:
            self.available = True

    # ------------------------------------------------------------------ #

    def model_path(self) -> str:
        return MODEL_FILE

    def _ensure_model(self):
        if self._model is not None:
            return self._model
        with self._lock:
            if self._model is not None:
                return self._model
            if not os.path.isfile(MODEL_FILE):
                raise EngineError(
                    "Модель Silero не найдена. Скачайте её: python -m voiceai.download_models"
                )
            try:
                import torch

                torch.set_num_threads(max(1, min(4, os.cpu_count() or 1)))
                model = torch.package.PackageImporter(MODEL_FILE).load_pickle(
                    "tts_models", "model"
                )
            except Exception as exc:
                raise EngineError(f"Не удалось загрузить модель: {exc}") from exc
            # прогрев: первый запуск JIT медленный, делаем его в фоне заранее
            try:
                model.apply_tts(
                    text="Прогрев.",
                    speaker="aidar",
                    sample_rate=24000,
                    put_accent=False,
                    put_yo=False,
                )
            except Exception:
                pass
            self._model = model
            return model

    def warmup(self) -> None:
        """Предзагрузка модели (вызывается сервером в фоновом потоке)."""
        if self.available:
            self._ensure_model()

    # ------------------------------------------------------------------ #

    def voices(self) -> List[Voice]:
        return list(SPEAKERS.values())

    def synthesize(
        self,
        text: str,
        voice_id: str,
        *,
        speed: float = 1.0,
        sample_rate: int = 48000,
        options: Optional[Dict] = None,
    ) -> SynthResult:
        if voice_id not in SPEAKERS:
            raise EngineError(f"Неизвестный голос «{voice_id}». Доступны: {', '.join(SPEAKERS)}")
        if sample_rate not in SAMPLE_RATES:
            raise EngineError(f"Частота {sample_rate} не поддерживается. Выберите {SAMPLE_RATES}")

        options = options or {}
        speed = float(speed)
        speed = max(0.25, min(2.0, speed))

        model = self._ensure_model()
        with self._lock:
            try:
                if abs(speed - 1.0) < 1e-3:
                    wav_tensor = model.apply_tts(
                        text=text,
                        speaker=voice_id,
                        sample_rate=sample_rate,
                        put_accent=bool(options.get("put_accent", True)),
                        put_yo=bool(options.get("put_yo", True)),
                    )
                else:
                    wav_tensor = model.apply_tts(
                        ssml_text=_ssml_with_rate(text, speed),
                        speaker=voice_id,
                        sample_rate=sample_rate,
                        put_accent=bool(options.get("put_accent", True)),
                        put_yo=bool(options.get("put_yo", True)),
                    )
            except AssertionError as exc:
                raise EngineError(str(exc)) from exc
            except Exception as exc:
                raise EngineError(f"Ошибка синтеза: {exc}") from exc

        wav_bytes = numpy_to_wav(wav_tensor.cpu().numpy(), sample_rate)
        return SynthResult(audio=wav_bytes, content_type="audio/wav",
                           sample_rate=sample_rate, ext="wav")
