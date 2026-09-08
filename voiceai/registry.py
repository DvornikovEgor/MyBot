"""Реестр движков синтеза: автоопределение доступных и удобный доступ к ним."""

from __future__ import annotations

import logging
from typing import Dict, List

from .engines.base import Engine, EngineError
from .engines.edge import EdgeEngine
from .engines.silero import SileroEngine

log = logging.getLogger("voiceai")


class Registry:
    def __init__(self) -> None:
        self.engines: List[Engine] = []
        self.errors: Dict[str, str] = {}
        self._discover()

    def _discover(self) -> None:
        for cls in (SileroEngine, EdgeEngine):
            try:
                engine = cls()
                self.engines.append(engine)
                if engine.available:
                    log.info("Движок доступен: %s", engine.title)
                else:
                    log.info("Движок недоступен: %s — %s", engine.title, engine.why_not)
            except Exception as exc:  # движок не должен ронять всё приложение
                self.errors[cls.__name__] = str(exc)
                log.exception("Не удалось инициализировать %s", cls.__name__)

    # ------------------------------------------------------------------ #

    def get(self, engine_id: str) -> Engine:
        for engine in self.engines:
            if engine.id == engine_id:
                return engine
        raise EngineError(f"Неизвестный движок «{engine_id}»")

    def default(self) -> Engine:
        """Первый доступный движок (офлайн имеют приоритет)."""
        for engine in self.engines:
            if engine.available:
                return engine
        raise EngineError(
            "Нет ни одного доступного движка синтеза. "
            "Для офлайн-режима скачайте модель: python -m voiceai.download_models"
        )

    def statuses(self) -> List[Dict]:
        return [engine.status() for engine in self.engines]
