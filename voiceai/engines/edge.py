"""Облачный движок на базе Microsoft Edge TTS (сотни голосов, нужен интернет).

Работает без ключей и регистрации. Если интернет недоступен (или доступ к
серверам Microsoft закрыт), движок аккуратно помечается как недоступный и
приложение продолжает работать на офлайн-движках.
"""

from __future__ import annotations

import asyncio
import socket
import threading
from typing import Dict, List, Optional

from .base import Engine, EngineError, SynthResult, Voice

_EDGE_HOST = "speech.platform.bing.com"
_VOICES_URL = (
    "https://speech.platform.bing.com/consumer/speech/synthesize/readaloud/"
    "voices/list?trustedclienttoken=6A5AA1D4EAFF4E9FB37E23D68491D6F4"
)
_CACHE_TTL = 3600

GENDERS = {"Male": "мужской", "Female": "женский"}


def _net_probe(timeout: float = 3.0) -> bool:
    """Проверка доступности серверов синтеза.

    Сначала быстрый TCP-коннект, затем настоящий (короткий) HTTPS-запрос:
    некоторые фаерволы пропускают TCP, но обрывают TLS.
    """
    try:
        with socket.create_connection((_EDGE_HOST, 443), timeout=timeout):
            pass
    except OSError:
        return False
    try:
        import urllib.request

        req = urllib.request.Request(_VOICES_URL, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status == 200
    except Exception:
        return False


class EdgeEngine(Engine):
    id = "edge"
    title = "Edge TTS (облако Microsoft)"
    kind = "cloud"

    def __init__(self) -> None:
        super().__init__()
        self._voices_cache: Optional[List[Voice]] = None
        self._cache_time = 0.0
        self._lock = threading.Lock()

        try:
            import edge_tts  # noqa: F401
        except Exception:
            self.why_not = "Пакет edge-tts не установлен: pip install edge-tts"
            return

        if _net_probe():
            self.available = True
        else:
            self.why_not = "Нет доступа к серверам синтеза (нужен интернет)"

    # ------------------------------------------------------------------ #

    def voices(self) -> List[Voice]:
        import time

        if not self.available:
            return []
        with self._lock:
            now = time.monotonic()
            if self._voices_cache is not None and now - self._cache_time < _CACHE_TTL:
                return self._voices_cache
            try:
                import edge_tts

                raw = asyncio.run(edge_tts.list_voices())
            except Exception as exc:
                self.available = False
                self.why_not = f"Не удалось получить список голосов: {exc}"
                return []
            voices = []
            for v in raw:
                short = v.get("ShortName", "")
                locale = v.get("Locale", "")
                voices.append(
                    Voice(
                        id=short,
                        name=short.split("-", 1)[-1].replace("Neural", "").strip(" -") or short,
                        gender=GENDERS.get(v.get("Gender", ""), ""),
                        lang=locale.split("-")[0],
                        description=f"{locale} · {v.get('Gender', '').lower()}",
                        preview_text="Привет! Так звучит мой голос." if locale.startswith("ru") else "Hello! This is how my voice sounds.",
                    )
                )
            self._voices_cache = voices
            self._cache_time = now
            return voices

    # ------------------------------------------------------------------ #

    def synthesize(
        self,
        text: str,
        voice_id: str,
        *,
        speed: float = 1.0,
        sample_rate: int = 24000,
        options: Optional[Dict] = None,
    ) -> SynthResult:
        if not self.available:
            raise EngineError(self.why_not or "Движок недоступен")

        speed = max(0.5, min(2.0, float(speed)))
        rate_pct = int(round((speed - 1.0) * 100))
        rate = f"{rate_pct:+d}%"

        try:
            import edge_tts

            async def run() -> bytes:
                comm = edge_tts.Communicate(text, voice_id, rate=rate)
                chunks = []
                async for chunk in comm.stream():
                    if chunk.get("type") == "audio":
                        chunks.append(chunk.get("data", b""))
                if not chunks:
                    raise EngineError("Сервер не вернул аудио")
                return b"".join(chunks)

            audio = asyncio.run(run())
        except EngineError:
            raise
        except Exception as exc:
            raise EngineError(f"Ошибка облачного синтеза: {exc}") from exc

        return SynthResult(audio=audio, content_type="audio/mpeg",
                           sample_rate=24000, ext="mp3")
