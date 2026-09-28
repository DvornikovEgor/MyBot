#!/usr/bin/env python3
"""
AI music director.

Turns a free-form chat conversation into a *recipe* — a fully specified musical
brief (style, mode, key, tempo, harmonic progressions) that the deterministic
composer in `js/composer.js` can render. The LLM decides the music; the Web
Audio engine plays it.

Provider: Google Gemini over the plain REST API (no third-party packages).
"""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from typing import Any

# --------------------------------------------------------------------------
# Vocabulary — must stay in sync with js/recipe.js
# --------------------------------------------------------------------------

STYLES = ["lofi", "synthwave", "ambient", "techno", "chiptune", "classical"]
MOODS = ["dreamy", "happy", "sad", "dark", "epic"]
SCALES = ["major", "minor", "harmonic", "dorian", "phrygian", "lydian", "mixolydian"]
DURATIONS = [30, 60, 90, 120]
HARMONIC_RHYTHMS = [0.5, 1.0, 2.0]

KEY_NAMES_RU = ["До", "До#", "Ре", "Ре#", "Ми", "Фа", "Фа#", "Соль", "Соль#", "Ля", "Ля#", "Си"]
STYLE_NAMES_RU = {
    "lofi": "Lo-fi",
    "synthwave": "Synthwave",
    "ambient": "Эмбиент",
    "techno": "Техно",
    "chiptune": "Chiptune",
    "classical": "Классика",
}
MOOD_NAMES_RU = {
    "dreamy": "Мечтательное",
    "happy": "Радостное",
    "sad": "Грустное",
    "dark": "Тёмное",
    "epic": "Эпичное",
}
SCALE_NAMES_RU = {
    "major": "мажор",
    "minor": "минор",
    "harmonic": "гармонический минор",
    "dorian": "дорийский",
    "phrygian": "фригийский",
    "lydian": "лидийский",
    "mixolydian": "миксолидийский",
}

DEFAULT_MODEL = "gemini-2.5-flash"
API_ROOT = "https://generativelanguage.googleapis.com/v1beta"
MAX_HISTORY = 12
TIMEOUT = 75


# --------------------------------------------------------------------------
# Config
# --------------------------------------------------------------------------


class Config:
    def __init__(self, env: dict[str, str] | None = None):
        env = os.environ if env is None else env
        self.api_key = (
            env.get("GEMINI_API_KEY")
            or env.get("GOOGLE_API_KEY")
            or env.get("GOOGLE_GENAI_API_KEY")
            or ""
        ).strip()
        self.model = (env.get("GEMINI_MODEL") or DEFAULT_MODEL).strip()
        # Override for tests / corporate proxies: must end with a slash.
        self.base_url = (env.get("GEMINI_BASE_URL") or API_ROOT).rstrip("/")
        # Offline dev mode: deterministic local stand-in, no network needed.
        self.fake = _as_bool(env.get("MYBOT_AI_FAKE"), False)
        self.timeout = float(env.get("GEMINI_TIMEOUT") or TIMEOUT)

    @property
    def ready(self) -> bool:
        return self.fake or bool(self.api_key)

    def public(self) -> dict[str, Any]:
        return {
            "provider": "fake" if self.fake else "gemini",
            "model": "local-stub" if self.fake else self.model,
            "ready": self.ready,
            "reason": None if self.ready else "no_key",
        }


def _as_bool(value: Any) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


# --------------------------------------------------------------------------
# Errors
# --------------------------------------------------------------------------


class DirectorError(Exception):
    """An error that should be reported to the browser, not as a 500."""

    def __init__(self, code: str, message: str, status: int = 502):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status


# --------------------------------------------------------------------------
# Prompt & schema
# --------------------------------------------------------------------------

SYSTEM_PROMPT = """\
Ты — «AI-дирижёр» музыкального генератора MyBot. Ты общаешься с пользователем на русском \
и превращаешь его слова в точный музыкальный рецепт, который локальный движок умеет исполнить.

ТЫ НЕ ВЫВОДИШЬ НОТЫ И НЕ ПИШЕШЬ ТЕКСТ ПЕСНИ. Ты выбираешь параметры, а звучит всё детерминированный \
синтезатор в браузере пользователя.

Возможности движка (жёсткие ограничения):
- Стиль задаёт инструменты и groove: lofi (мягкое FM-пиано, винил, свинг), synthwave (широкие пэды, \
кислотный бас, 1/8 дилей), ambient (воздушные пэды, длинные ноты, БЕЗ барабанов), \
techno (ровный бас-кик, секвенции, без мелодии-соло в духе acid), chiptune (квадратные волны, \
мелкие секвенции), classical (струнные, арпеджированный аккомпанемент, БЕЗ барабанов).
- Настроение влияет на энергию, яркость и темп: dreamy, happy, sad, dark, epic.
- Лад (scale) выбирается явно: major, minor, harmonic (гармонический минор), dorian, phrygian, \
lydian, mixolydian. Это влияет и на мелодию, и на аккорды.
- Тональность key: 0..11 = До, До#, Ре, Ре#, Ми, Фа, Фа#, Соль, Соль#, Ля, Ля#, Си.
- Темп bpm: 60..150, либо 0 — «пусть движок подберёт сам» в стиле.
- harmonicRhythm: сколько аккордов в такте. 0.5 — аккорд на 2 такта (просторно), \
1 — аккорд на такт (обычно), 2 — два аккорда на такт (движение).
- Прогрессии — массивы ступеней лада от 0 (тоника) до 6 (септима), 2..6 ступеней в аккорде. \
Пример: [0,5,2,6] — i–VI–III–VII, классика синтвейва; [0,3,4,0] — I–IV–V–I.
- progressionA — основная часть, progressionB — контрастная (припев).
- seed — короткая строка-идентификатор (до 24 символов). Сохраняй прежний seed, если пользователь \
не просит новое: тогда «тот же трек в другой тональности» реально получится.

ПРАВИЛА ОТВЕТА:
1. Отвечай живым, коротким текстом (1–3 предложения): что именно ты сделал и почему. Без markdown-заголовков.
2. Если пользователь просто болтает, задаёт вопрос или просит «что умеешь» — не меняй настройки \
(apply=false), но всё равно верни рецепт с текущими параметрами.
3. Если просят убрать барабаны — бери ambient или classical (у них их нет в движке). \
Ускорить — повышай bpm. Успокоить/замедлить — понижай. Короче — уменьшай duration.
4. Учитывай контекст диалога: «сделай темнее» меняет mood/scale, а не всё с нуля.
5. Прогрессии подбирай осмысленно под стиль и настроение, не выдавай один и тот же набор.
6. title — короткое красивое название трека до 40 символов. notes — одно предложение о том, что \
используешь (например: «i–VI–III–VII, фигуры-квинты в мелодии»).
"""

RECIPE_SCHEMA: dict[str, Any] = {
    "type": "OBJECT",
    "properties": {
        "reply": {"type": "STRING", "description": "Ответ пользователю на русском, 1–3 предложения."},
        "title": {"type": "STRING", "description": "Название трека, до 40 символов."},
        "apply": {"type": "BOOLEAN", "description": "Применить рецепт и пересобрать трек."},
        "seed": {"type": "STRING", "description": "Короткий идентификатор трека, до 24 символов."},
        "style": {"type": "STRING", "enum": STYLES},
        "mood": {"type": "STRING", "enum": MOODS},
        "key": {"type": "INTEGER", "description": "0..11: До, До#, Ре, Ре#, Ми, Фа, Фа#, Соль, Соль#, Ля, Ля#, Си."},
        "scale": {"type": "STRING", "enum": SCALES},
        "bpm": {"type": "INTEGER", "description": "60..150 или 0 — темп подберёт движок."},
        "duration": {"type": "INTEGER", "enum": DURATIONS},
        "harmonicRhythm": {"type": "NUMBER", "enum": HARMONIC_RHYTHMS},
        "progressionA": {
            "type": "ARRAY",
            "items": {"type": "INTEGER", "minimum": 0, "maximum": 6},
            "description": "Ступени лада 0..6, 2..6 аккордов.",
        },
        "progressionB": {
            "type": "ARRAY",
            "items": {"type": "INTEGER", "minimum": 0, "maximum": 6},
            "description": "Контрастная прогрессия, ступени 0..6, 2..6 аккордов.",
        },
        "notes": {"type": "STRING", "description": "Одно предложение о музыкальном решении."},
    },
    "required": [
        "reply",
        "apply",
        "seed",
        "style",
        "mood",
        "key",
        "scale",
        "bpm",
        "duration",
        "harmonicRhythm",
        "progressionA",
        "progressionB",
    ],
}


# --------------------------------------------------------------------------
# Recipe normalisation — the last line of defence before the composer sees it
# --------------------------------------------------------------------------


def _as_int(value: Any, default: int) -> int:
    try:
        return int(round(float(value)))
    except (TypeError, ValueError):
        return default


def _as_float(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _as_bool(value: Any, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return _as_bool_str(value, default)
    return default


def _as_bool_str(value: str, default: bool) -> bool:
    v = value.strip().lower()
    if v in {"1", "true", "yes", "on"}:
        return True
    if v in {"0", "false", "no", "off"}:
        return False
    return default


def _pick(value: Any, allowed: list, default):
    return value if isinstance(value, str) and value in allowed else default


def normalise_progression(value: Any) -> list[int] | None:
    """Keep only sane degree arrays: 2..6 integers within 0..6."""
    if not isinstance(value, list):
        return None
    degrees = []
    for item in value:
        if isinstance(item, bool) or not isinstance(item, (int, float)):
            return None
        degrees.append(int(round(item)))
    if not (2 <= len(degrees) <= 6):
        return None
    if any(d < 0 or d > 6 for d in degrees):
        return None
    return degrees


def normalise_recipe(raw: Any, current: dict[str, Any] | None = None) -> dict[str, Any]:
    """Clamp/validate whatever the model produced into a renderable recipe."""
    current = current or {}
    cur_recipe = current.get("recipe") if isinstance(current.get("recipe"), dict) else {}
    cur = cur_recipe or current  # accept both shapes

    raw = raw if isinstance(raw, dict) else {}
    out: dict[str, Any] = {}

    reply = raw.get("reply")
    out["reply"] = (reply.strip() if isinstance(reply, str) and reply.strip() else "Готово — собрал новый трек.")
    out["title"] = _clean_text(raw.get("title"), 40) or _clean_text(cur.get("title"), 40) or "Без названия"
    out["notes"] = _clean_text(raw.get("notes"), 200)
    out["apply"] = _as_bool(raw.get("apply"), True)

    out["seed"] = _clean_text(raw.get("seed"), 24) or _clean_text(cur.get("seed"), 24) or "track"

    out["style"] = _pick(raw.get("style"), STYLES, cur.get("style") if cur.get("style") in STYLES else "lofi")
    out["mood"] = _pick(raw.get("mood"), MOODS, cur.get("mood") if cur.get("mood") in MOODS else "dreamy")
    out["scale"] = _pick(raw.get("scale"), SCALES, cur.get("scale") if cur.get("scale") in SCALES else "minor")

    key = _as_int(raw.get("key", cur.get("key", 0)), 0)
    out["key"] = key % 12

    bpm = _as_int(raw.get("bpm", cur.get("bpm", 0)), 0)
    if bpm == 0:
        out["bpm"] = 0  # let the engine pick
    else:
        out["bpm"] = max(60, min(150, bpm))

    duration = _as_int(raw.get("duration", cur.get("duration", 60)), 60)
    out["duration"] = min(DURATIONS, key=lambda d: abs(d - duration))

    hr = _as_float(raw.get("harmonicRhythm", cur.get("harmonicRhythm", 1)), 1.0)
    out["harmonicRhythm"] = min(HARMONIC_RHYTHMS, key=lambda h: abs(h - hr))

    prog_a = normalise_progression(raw.get("progressionA")) or normalise_progression(cur.get("progressionA"))
    prog_b = normalise_progression(raw.get("progressionB")) or normalise_progression(cur.get("progressionB"))
    out["progressionA"] = prog_a or [0, 5, 2, 6]
    out["progressionB"] = prog_b or [0, 3, 4, 0]
    if out["progressionB"] == out["progressionA"]:
        out["progressionB"] = [0, 3, 4, 0] if out["progressionA"] != [0, 3, 4, 0] else [0, 6, 5, 6]

    return out


def _clean_text(value: Any, limit: int) -> str:
    if not isinstance(value, str):
        return ""
    text = " ".join(value.split())
    return text[:limit]


def describe(recipe: dict[str, Any]) -> list[tuple[str, str]]:
    """Human-readable summary used by the UI recipe card."""
    rows = [
        ("Стиль", STYLE_NAMES_RU.get(recipe["style"], recipe["style"])),
        ("Настроение", MOOD_NAMES_RU.get(recipe["mood"], recipe["mood"])),
        ("Тональность", f"{KEY_NAMES_RU[recipe['key']]} {SCALE_NAMES_RU.get(recipe['scale'], recipe['scale'])}"),
        ("Темп", f"{recipe['bpm']} BPM" if recipe["bpm"] else "подберёт движок"),
        ("Длина", f"~{recipe['duration']} с"),
        (
            "Гармония",
            f"{recipe['harmonicRhythm']:g} акк./такт · {_roman(recipe['progressionA'])} · {_roman(recipe['progressionB'])}",
        ),
    ]
    return rows


ROMAN = ["I", "II", "III", "IV", "V", "VI", "VII"]


def _roman(degrees: list[int]) -> str:
    return "–".join(ROMAN[d % 7] for d in degrees)


# --------------------------------------------------------------------------
# Gemini transport
# --------------------------------------------------------------------------


def build_payload(messages: list[dict[str, str]], current: dict[str, Any] | None) -> dict[str, Any]:
    """Assemble the generateContent request body."""
    contents = []
    for msg in messages[-MAX_HISTORY:]:
        text = msg.get("text")
        if not isinstance(text, str) or not text.strip():
            continue
        role = "model" if msg.get("role") == "model" else "user"
        contents.append({"role": role, "parts": [{"text": text.strip()}]})
    if not contents:
        contents = [{"role": "user", "parts": [{"text": "Придумай трек."}]}]

    state = _state_block(current)
    contents[-1]["parts"][0]["text"] = f"{contents[-1]['parts'][0]['text']}\n\n{state}"

    return {
        "systemInstruction": {"parts": [{"text": SYSTEM_PROMPT}]},
        "contents": contents,
        "generationConfig": {
            "temperature": 0.95,
            "topP": 0.95,
            "maxOutputTokens": 2048,
            "responseMimeType": "application/json",
            "responseSchema": RECIPE_SCHEMA,
        },
        "safetySettings": [
            {"category": cat, "threshold": "BLOCK_ONLY_HIGH"}
            for cat in (
                "HARM_CATEGORY_HARASSMENT",
                "HARM_CATEGORY_HATE_SPEECH",
                "HARM_CATEGORY_SEXUALLY_EXPLICIT",
                "HARM_CATEGORY_DANGEROUS_CONTENT",
            )
        ],
    }


def _state_block(current: dict[str, Any] | None) -> str:
    """Tell the model what is on the mixer right now, so replies can be relative."""
    current = current or {}
    recipe = current.get("recipe") if isinstance(current.get("recipe"), dict) else None
    source = recipe or current
    if not source:
        return "Сейчас в микшере ничего не выбрано."
    parts = [
        f"Сейчас в генераторе: стиль {source.get('style')}, настроение {source.get('mood')}, "
        f"лад {source.get('scale')}, тональность {source.get('key')}, "
        f"темп {source.get('bpm') or 'авто'}, длина {source.get('duration')} с, "
        f"прогрессии A={source.get('progressionA')} B={source.get('progressionB')}, "
        f"сид {source.get('seed')!r}."
    ]
    comp = current.get("comp")
    if isinstance(comp, dict):
        chords = [f"{c.get('bar')}:{c.get('root')}" for c in (comp.get("chords") or [])[:8]]
        if chords:
            parts.append("Начало гармонии текущего трека (такт:миди): " + ", ".join(chords) + ".")
    return " ".join(parts)


def _request(url: str, payload: dict[str, Any] | None, method: str, timeout: float) -> dict[str, Any]:
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    req.add_header("Accept", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:  # noqa: PERF203 - explicit mapping below
        body = exc.read().decode("utf-8", "replace")
        raise _map_http_error(exc.code, body) from exc
    except urllib.error.URLError as exc:
        raise DirectorError(
            "network",
            "Не удалось достучаться до Gemini API. Проверь интернет и доступ к "
            "generativelanguage.googleapis.com.",
            502,
        ) from exc
    except TimeoutError as exc:
        raise DirectorError("timeout", "Gemini API не ответил вовремя. Попробуй ещё раз.", 504) from exc
    except json.JSONDecodeError as exc:
        raise DirectorError("bad_response", "Gemini вернул не-JSON ответ.", 502) from exc


def _map_http_error(code: int, body: str) -> DirectorError:
    detail = ""
    try:
        payload = json.loads(body)
        detail = payload.get("error", {}).get("message", "") or payload.get("error", {}).get("status", "")
    except json.JSONDecodeError:
        detail = body[:300]
    low = (detail or "").lower()

    if code == 400 and "api key" in low:
        return DirectorError("bad_key", "Ключ Gemini API отклонён. Проверь GEMINI_API_KEY.", 401)
    if code in (401, 403):
        return DirectorError("bad_key", "Доступ к Gemini API запрещён. Проверь ключ и квоту.", 401)
    if code == 404:
        return DirectorError("model_not_found", f"Модель не найдена: {detail or code}", 502)
    if code == 429:
        return DirectorError("quota", "Исчерпана квота Gemini API. Попробуй позже.", 429)
    if code >= 500:
        return DirectorError("upstream", f"Gemini API вернул ошибку {code}: {detail or 'без деталей'}", 502)
    return DirectorError("upstream", f"Gemini API вернул ошибку {code}: {detail or 'без деталей'}", 502)


def _strip_schema(payload: dict[str, Any]) -> dict[str, Any]:
    """Retry payload for older/stricter endpoints: keep the contract, drop the schema."""
    slim = json.loads(json.dumps(payload))
    gen = slim.get("generationConfig", {})
    gen.pop("responseSchema", None)
    gen.pop("thinkingConfig", None)
    slim.pop("safetySettings", None)
    return slim


def _extract_text(data: dict[str, Any]) -> str:
    candidates = data.get("candidates") or []
    if not candidates:
        feedback = data.get("promptFeedback") or {}
        block = feedback.get("blockReason")
        if block:
            raise DirectorError("blocked", f"Запрос заблокирован моделью ({block}).", 400)
        raise DirectorError("empty", "Модель вернула пустой ответ.", 502)
    finish = candidates[0].get("finishReason")
    parts = (candidates[0].get("content") or {}).get("parts") or []
    text = "".join(p.get("text", "") for p in parts if isinstance(p, dict))
    if not text.strip():
        if finish == "SAFETY" or finish == "PROHIBITED_CONTENT":
            raise DirectorError("blocked", "Ответ не прошёл фильтр безопасности. Переформулируй запрос.", 400)
        raise DirectorError("empty", f"Модель вернула пустой ответ (finishReason: {finish or '—'}).", 502)
    return text


def discover_model(config: Config) -> str | None:
    """Ask the API which models this key can use; used when a name 404s."""
    url = f"{config.base_url}/models?key={urllib.request.quote(config.api_key)}&pageSize=200"
    try:
        data = _request(url, None, "GET", config.timeout)
    except DirectorError:
        return None
    names = []
    for model in data.get("models") or []:
        name = model.get("name") or ""
        if "generateContent" not in (model.get("supportedGenerationMethods") or []):
            continue
        short = name.split("/")[-1]
        if any(tag in short for tag in ("-image", "-tts", "-embedding", "-aqa", "-native-audio")):
            continue
        names.append(short)
    if not names:
        return None
    flash = [n for n in names if "flash" in n.lower()]
    return (flash or names)[0]


# --------------------------------------------------------------------------
# Public API
# --------------------------------------------------------------------------


def chat(messages: list[dict[str, str]], current: dict[str, Any] | None = None,
         config: Config | None = None) -> dict[str, Any]:
    """Run one turn of the conversation. Returns {reply, recipe, model, ...}."""
    config = config or Config()
    if not config.ready:
        raise DirectorError(
            "no_key",
            "Ключ Gemini API не задан. Запусти сервер с GEMINI_API_KEY=... — "
            "подробности в README.",
            503,
        )
    if config.fake:
        return _fake_turn(messages, current)

    payload = build_payload(messages, current)
    model = config.model
    url = f"{config.base_url}/models/{model}:generateContent?key={config.api_key}"

    try:
        data = _request(url, payload, "POST", config.timeout)
    except DirectorError as exc:
        retryable = exc.code in {"model_not_found"} or (
            exc.status == 502 and exc.code == "upstream"
        )
        if not retryable:
            raise
        if exc.code == "model_not_found":
            found = discover_model(config)
            if not found:
                raise DirectorError(
                    "model_not_found",
                    f"Модель {model} недоступна для этого ключа и подобрать замену не удалось.",
                    502,
                )
            model = found
        # Schema/thinking config may be rejected by some deployments — retry lean.
        url = f"{config.base_url}/models/{model}:generateContent?key={config.api_key}"
        try:
            data = _request(url, _strip_schema(payload), "POST", config.timeout)
        except DirectorError:
            raise exc

    try:
        parsed = json.loads(_extract_text(data))
    except json.JSONDecodeError as exc:
        raise DirectorError("bad_json", "Модель вернула невалидный JSON рецепта.", 502) from exc

    recipe = normalise_recipe(parsed, current)
    usage = (data.get("usageMetadata") or {})
    return {
        "reply": recipe["reply"],
        "recipe": recipe,
        "model": model,
        "usage": {
            "promptTokens": usage.get("promptTokenCount"),
            "outputTokens": usage.get("candidatesTokenCount"),
        },
    }


def health(config: Config | None = None) -> dict[str, Any]:
    config = config or Config()
    info = config.public()
    if not info["ready"]:
        info["message"] = (
            "Ключ Gemini API не найден. Задайте переменную окружения GEMINI_API_KEY "
            "и перезапустите сервер — ИИ заработает."
        )
    return info


# --------------------------------------------------------------------------
# Offline stand-in (MYBOT_AI_FAKE=1) — for UI work and tests without a key
# --------------------------------------------------------------------------

_FAKE_KEYWORDS = [
    (r"дожд|ноч|тоск|груст|печал|sad|грустн", "sad"),
    (r"злой|тёмн|страш|мрач|dark|тёмн", "dark"),
    (r"радост|весел|смеш|счаст|happy|радостн|празд", "happy"),
    (r"мечт|сон|неб|воздуш|dreamy|мечтат|косм", "dreamy"),
    (r"герой|эпич|мощ|битва|epic|эпичн", "epic"),
]
_FAKE_STYLES = [
    (r"дожд|ноч|уют|кофе|учеб|груст", "lofi"),
    (r"ретро|волн|неон|синтвейв|80|машина|synthwave", "synthwave"),
    (r"спокой|тиш|медит|косм|ambient|эмбиент|сон", "ambient"),
    (r"клуб|танц|техно|техно|techno|днс|рейв", "techno"),
    (r"8-бит|игр|пиксел|chiptune|чиптюн|марио", "chiptune"),
    (r"классик|симфони|фортепи|шопен|classical|классик|бетховен", "classical"),
]


def _fake_turn(messages: list[dict[str, str]], current: dict[str, Any] | None) -> dict[str, Any]:
    last_user = ""
    for msg in reversed(messages or []):
        if msg.get("role") == "user" and isinstance(msg.get("text"), str):
            last_user = msg["text"].lower()
            break
    base = normalise_recipe({}, current)
    style = _match(_FAKE_STYLES, last_user, base["style"])
    mood = _match(_FAKE_KEYWORDS, last_user, base["mood"])
    bpm = 0
    found = re.search(r"(\d{2,3})\s*(bpm|бпм|темп)", last_user)
    if found:
        bpm = max(60, min(150, int(found.group(1))))
    duration = base["duration"]
    found = re.search(r"(\d{2,3})\s*(с|сек|second)", last_user)
    if found:
        duration = min(DURATIONS, key=lambda d: abs(d - int(found.group(1))))
    recipe = normalise_recipe(
        {
            "reply": "Это локальная заглушка (MYBOT_AI_FAKE=1), а не Gemini. Подключи ключ — и дирижёр ответит по-настоящему.",
            "title": "Локальная заглушка",
            "apply": True,
            "style": style,
            "mood": mood,
            "bpm": bpm,
            "duration": duration,
        },
        current,
    )
    return {"reply": recipe["reply"], "recipe": recipe, "model": "local-stub", "usage": {}}


def _match(rules: list[tuple[str, str]], text: str, default: str) -> str:
    for pattern, value in rules:
        if re.search(pattern, text):
            return value
    return default
