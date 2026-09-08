"""Утилиты работы со звуком (WAV, 16 бит, моно)."""

from __future__ import annotations

import io
import wave


def numpy_to_wav(samples, sample_rate: int) -> bytes:
    """Превращает одномерный numpy-массив float32 [-1..1] в байты WAV."""
    import numpy as np

    samples = np.asarray(samples, dtype=np.float32).reshape(-1)
    samples = samples.clip(-1.0, 1.0)
    pcm = (samples * 32767.0).astype("<i2")

    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sample_rate)
        w.writeframes(pcm.tobytes())
    return buf.getvalue()


def wav_duration(wav_bytes: bytes) -> float:
    """Длительность WAV в секундах."""
    try:
        with wave.open(io.BytesIO(wav_bytes)) as w:
            return w.getnframes() / float(w.getframerate() or 1)
    except Exception:
        return 0.0
