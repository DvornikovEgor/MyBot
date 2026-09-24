"""
Опциональный модуль: умный ассистент через LLM API (OpenAI-совместимый).

Работает БЕЗ дополнительных библиотек — только urllib из стандартной поставки.
Ключ и настройки читаются из переменных окружения:

    LLM_API_KEY    — API-ключ (или OPENAI_API_KEY, если первое не задано)
    LLM_BASE_URL   — базовый URL API (по умолчанию https://api.openai.com/v1)
                     Так работают и OpenAI, и Groq, и OpenRouter, и локальный
                     LM Studio / Ollama с OpenAI-совместимым сервером.
    LLM_MODEL      — модель (по умолчанию gpt-4o-mini)

Если ключа нет — функции просто возвращают None, и веб-интерфейс честно
сообщает, что ассистент не настроен. Остальной функционал (нейросеть)
работает полностью локально и без ключей.
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import List, Optional

SYSTEM_PROMPT = (
    "Ты — дружелюбный ассистент проекта MyBot AI. Проект демонстрирует "
    "полносвязную нейросеть, написанную с нуля на NumPy (без PyTorch и "
    "TensorFlow), которая распознаёт рукописные цифры. Отвечай кратко и "
    "по-русски. Если спрашивают про устройство нейросети — объясняй простыми "
    "словами: прямой проход, backpropagation, оптимизатор Adam."
)


def is_configured() -> bool:
    return bool(os.environ.get("LLM_API_KEY") or os.environ.get("OPENAI_API_KEY"))


def get_settings() -> dict:
    return {
        "api_key": os.environ.get("LLM_API_KEY") or os.environ.get("OPENAI_API_KEY", ""),
        "base_url": (os.environ.get("LLM_BASE_URL") or "https://api.openai.com/v1").rstrip("/"),
        "model": os.environ.get("LLM_MODEL") or "gpt-4o-mini",
    }


def chat(messages: List[dict], temperature: float = 0.6) -> Optional[str]:
    """Отправляет диалог в LLM API. Возвращает текст ответа или None при ошибке."""
    if not is_configured():
        return None
    s = get_settings()
    payload = json.dumps({
        "model": s["model"],
        "messages": [{"role": "system", "content": SYSTEM_PROMPT}] + messages,
        "temperature": temperature,
    }).encode("utf-8")

    req = urllib.request.Request(
        s["base_url"] + "/chat/completions",
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {s['api_key']}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        return data["choices"][0]["message"]["content"]
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:300]
        raise RuntimeError(f"LLM API вернул ошибку {exc.code}: {detail}") from exc
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(f"Не удалось обратиться к LLM API: {exc}") from exc
