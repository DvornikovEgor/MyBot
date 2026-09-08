"""Базовые типы для движков синтеза речи."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional


class EngineError(RuntimeError):
    """Ошибка движка синтеза (показывается пользователю как есть)."""


@dataclass
class Voice:
    """Один голос в каталоге движка."""

    id: str                 # уникальный id внутри движка
    name: str               # человекочитаемое имя
    gender: str = ""        # «мужской» / «женский» / ...
    lang: str = "ru"        # код языка (для группировки)
    description: str = ""   # короткое описание тембра
    preview_text: str = ""  # фраза-образец для прослушивания


@dataclass
class SynthResult:
    """Результат синтеза."""

    audio: bytes            # байты аудиофайла
    content_type: str       # например "audio/wav" или "audio/mpeg"
    sample_rate: int = 0    # частота дискретизации (0 — неизвестна)
    ext: str = "wav"        # расширение файла


class Engine:
    """Интерфейс движка синтеза речи.

    Движок может быть в трёх состояниях:
      * доступен (available == True) — готов синтезировать;
      * нужна модель (needs_model == True) — установлен, но нет файла модели;
      * недоступен — нет зависимостей или сети.
    """

    id: str = "engine"
    title: str = "Движок"
    kind: str = "offline"   # "offline" | "cloud"

    def __init__(self) -> None:
        self.available: bool = False
        self.needs_model: bool = False
        self.why_not: str = ""

    # --- API для реализации -------------------------------------------------

    def voices(self) -> List[Voice]:
        raise NotImplementedError

    def synthesize(
        self,
        text: str,
        voice_id: str,
        *,
        speed: float = 1.0,
        sample_rate: int = 48000,
        options: Optional[Dict] = None,
    ) -> SynthResult:
        raise NotImplementedError

    # --- сериализация --------------------------------------------------------

    def status(self) -> Dict:
        return {
            "id": self.id,
            "title": self.title,
            "kind": self.kind,
            "available": self.available,
            "needs_model": self.needs_model,
            "why_not": self.why_not,
        }
