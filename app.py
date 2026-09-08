#!/usr/bin/env python3
"""Голосовой ИИ — приложение, которое умеет делать голоса.

Возможности
-----------
* Веб-интерфейс: текст → выбор голоса → озвучка нейросетью.
* Офлайн-движок на нейросети Silero v4 (6 русских голосов).
* Облачный движок Edge TTS (сотни голосов на разных языках, нужен интернет).
* Командная строка: озвучка одной командой.

Быстрый старт
-------------
    python app.py serve                 # веб-интерфейс на http://127.0.0.1:8000
    python app.py say "Привет, мир!"    # озвучить фразу в файл
    python app.py voices                # список доступных голосов
    python app.py download-models       # скачать нейромодель (если её нет)
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import threading
import time
from typing import Dict, Optional

from flask import Flask, Response, jsonify, request, send_file, send_from_directory

from voiceai import __version__
from voiceai.download_models import download_model, DownloadError
from voiceai.engines.base import EngineError
from voiceai.engines.xtts import LANGUAGES, SAMPLES_DIR, XTTSEngine
from voiceai.registry import Registry

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
WEBUI_DIR = os.path.join(BASE_DIR, "webui")
OUTPUT_DIR = os.path.join(BASE_DIR, "outputs")
MANIFEST = os.path.join(OUTPUT_DIR, "manifest.json")
MAX_TEXT_LEN = 2000
MAX_CLONE_TEXT_LEN = 600
MAX_HISTORY = 30

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
log = logging.getLogger("mybot")

registry = Registry()

# --------------------------------------------------------------------------- #
#  История озвучек (простой JSON-манифест в каталоге outputs/)                 #
# --------------------------------------------------------------------------- #

_manifest_lock = threading.Lock()


def _load_manifest() -> list:
    try:
        with open(MANIFEST, encoding="utf-8") as fh:
            data = json.load(fh)
            return data if isinstance(data, list) else []
    except Exception:
        return []


def _save_manifest(items: list) -> None:
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    with open(MANIFEST, "w", encoding="utf-8") as fh:
        json.dump(items[-MAX_HISTORY:], fh, ensure_ascii=False, indent=1)


def _add_history(entry: Dict) -> None:
    with _manifest_lock:
        items = _load_manifest()
        items.append(entry)
        _save_manifest(items)


def _safe_filename(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]", "_", name)


# --------------------------------------------------------------------------- #
#  Загрузка модели в фоне                                                      #
# --------------------------------------------------------------------------- #

_model_job: Dict = {"state": "idle", "progress": 0, "message": ""}
_model_job_lock = threading.Lock()


def _run_model_download() -> None:
    def progress(title: str, done: int, total: int) -> None:
        with _model_job_lock:
            _model_job["message"] = title
            _model_job["progress"] = round(done / total * 100, 1) if total else 0

    with _model_job_lock:
        _model_job.update(state="working", progress=0, message="подключение…")
    try:
        path = download_model(on_progress=progress)
        engine = registry.get("silero")
        engine.needs_model = False
        engine.available = True
        engine.why_not = ""
        with _model_job_lock:
            _model_job.update(state="done", progress=100, message=f"Модель сохранена: {path}")
        log.info("Модель скачана: %s", path)
        threading.Thread(target=engine.warmup, daemon=True).start()
    except DownloadError as exc:
        with _model_job_lock:
            _model_job.update(state="error", message=str(exc))
        log.error("Ошибка загрузки модели: %s", exc)


# --------------------------------------------------------------------------- #
#  Клонирование голоса (движок инициализируется в фоне, чтобы не              #
#  задерживать запуск сервера тяжёлым импортом библиотеки TTS)                #
# --------------------------------------------------------------------------- #

_clone_engine: Optional[XTTSEngine] = None
_clone_state = {"state": "loading"}
_clone_job: Dict = {"state": "idle", "progress": 0, "message": ""}
_clone_job_lock = threading.Lock()


def _clone_engine_worker() -> None:
    global _clone_engine
    try:
        _clone_engine = XTTSEngine()
    except Exception as exc:  # библиотека может быть не установлена
        _clone_engine = None
        _clone_state["why_not"] = str(exc)
    _clone_state["state"] = "ready"


def _run_clone_model_download() -> None:
    def progress(done: int, total: int, name: str) -> None:
        with _clone_job_lock:
            _clone_job["message"] = name
            _clone_job["progress"] = round(done / total * 100, 1) if total > 0 else 0

    with _clone_job_lock:
        _clone_job.update(state="working", progress=0, message="подключение…")
    try:
        path = _clone_engine.download_model(on_progress=progress)
        _clone_engine.needs_model = False
        _clone_engine.available = True
        _clone_engine.why_not = ""
        with _clone_job_lock:
            _clone_job.update(state="done", progress=100, message=f"Модель сохранена: {path}")
        log.info("Модель клонирования скачана: %s", path)
        threading.Thread(target=_clone_engine.warmup, daemon=True).start()
    except Exception as exc:
        with _clone_job_lock:
            _clone_job.update(state="error", message=str(exc))
        log.error("Ошибка загрузки модели клонирования: %s", exc)


_TRANSLIT = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "yo",
    "ж": "zh", "з": "z", "и": "i", "й": "y", "к": "k", "л": "l", "м": "m",
    "н": "n", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t", "у": "u",
    "ф": "f", "х": "h", "ц": "ts", "ч": "ch", "ш": "sh", "щ": "sch",
    "ъ": "", "ы": "y", "ь": "", "э": "e", "ю": "yu", "я": "ya",
}


def _slugify(name: str) -> str:
    """Имя → безопасный slug (только ASCII): папки и URL без сюрпризов."""
    text = name.lower()
    text = "".join(_TRANSLIT.get(ch, ch) for ch in text)
    slug = re.sub(r"[^a-z0-9]+", "-", text).strip("-")[:40]
    return slug or time.strftime("voice-%H%M%S")


# --------------------------------------------------------------------------- #
#  Flask-приложение                                                            #
# --------------------------------------------------------------------------- #

def create_app() -> Flask:
    app = Flask(__name__, static_folder=None)

    @app.get("/")
    def index():
        return send_from_directory(WEBUI_DIR, "index.html")

    @app.get("/api/status")
    def api_status():
        silero = registry.get("silero") if any(e.id == "silero" for e in registry.engines) else None
        return jsonify({
            "version": __version__,
            "engines": registry.statuses(),
            "errors": registry.errors,
            "model_job": dict(_model_job),
            "silero_model_exists": bool(silero and os.path.isfile(silero.model_path())),
        })

    @app.get("/api/voices")
    def api_voices():
        result = []
        for engine in registry.engines:
            if not engine.available:
                continue
            try:
                voices = engine.voices()
            except Exception as exc:
                log.warning("Не удалось получить голоса %s: %s", engine.id, exc)
                continue
            for voice in voices:
                result.append({
                    "engine": engine.id,
                    "engine_title": engine.title,
                    "kind": engine.kind,
                    "id": voice.id,
                    "name": voice.name,
                    "gender": voice.gender,
                    "lang": voice.lang,
                    "description": voice.description,
                    "preview_text": voice.preview_text,
                })
        return jsonify({"voices": result, "count": len(result)})

    @app.post("/api/say")
    def api_say():
        data = request.get_json(silent=True) or {}
        text = (data.get("text") or "").strip()
        if not text:
            return jsonify({"error": "Введите текст"}), 400
        if len(text) > MAX_TEXT_LEN:
            return jsonify({"error": f"Слишком длинный текст (максимум {MAX_TEXT_LEN} символов)"}), 400

        voice_ref = data.get("voice") or ""
        if "/" not in voice_ref:
            engine = registry.default()
            voice_id = voice_ref or (engine.voices()[0].id if engine.voices() else "")
        else:
            engine_name, voice_id = voice_ref.split("/", 1)
            try:
                engine = registry.get(engine_name)
            except EngineError as exc:
                return jsonify({"error": str(exc)}), 400

        if not engine.available:
            return jsonify({"error": f"Движок «{engine.title}» недоступен: {engine.why_not}"}), 400

        try:
            speed = float(data.get("speed", 1.0))
            sample_rate = int(data.get("sample_rate", 48000))
        except (TypeError, ValueError):
            return jsonify({"error": "Некорректные параметры скорости/частоты"}), 400
        options = {
            "put_accent": bool(data.get("put_accent", True)),
            "put_yo": bool(data.get("put_yo", True)),
        }

        started = time.time()
        try:
            result = engine.synthesize(text, voice_id, speed=speed,
                                       sample_rate=sample_rate, options=options)
        except EngineError as exc:
            return jsonify({"error": str(exc)}), 400
        except Exception as exc:
            log.exception("Ошибка синтеза")
            return jsonify({"error": f"Внутренняя ошибка синтеза: {exc}"}), 500
        synth_ms = int((time.time() - started) * 1000)

        os.makedirs(OUTPUT_DIR, exist_ok=True)
        voice_name = next((v.name for v in engine.voices() if v.id == voice_id), voice_id)
        stamp = time.strftime("%Y%m%d-%H%M%S")
        filename = _safe_filename(f"{stamp}_{engine.id}-{voice_id}.{result.ext}")
        path = os.path.join(OUTPUT_DIR, filename)
        with open(path, "wb") as fh:
            fh.write(result.audio)

        try:
            import wave
            with wave.open(path, "rb") as w:
                seconds = round(w.getnframes() / w.getframerate(), 2)
        except Exception:
            seconds = None

        entry = {
            "file": filename,
            "url": f"/audio/{filename}",
            "text": text[:140] + ("…" if len(text) > 140 else ""),
            "engine": engine.id,
            "voice": voice_id,
            "voice_name": voice_name,
            "speed": speed,
            "seconds": seconds,
            "synth_ms": synth_ms,
            "ts": stamp,
        }
        _add_history(entry)
        return jsonify(entry)

    @app.get("/api/history")
    def api_history():
        items = [i for i in reversed(_load_manifest())
                 if os.path.isfile(os.path.join(OUTPUT_DIR, i.get("file", "")))]
        return jsonify({"items": items})

    @app.post("/api/history/clear")
    def api_history_clear():
        with _manifest_lock:
            for item in _load_manifest():
                try:
                    os.remove(os.path.join(OUTPUT_DIR, item.get("file", "")))
                except OSError:
                    pass
            _save_manifest([])
        return jsonify({"ok": True})

    @app.get("/audio/<path:name>")
    def audio(name: str):
        safe = _safe_filename(name)
        full = os.path.join(OUTPUT_DIR, safe)
        if not os.path.isfile(full):
            return jsonify({"error": "Файл не найден"}), 404
        mime = "audio/mpeg" if safe.endswith(".mp3") else "audio/wav"
        return send_file(full, mimetype=mime)

    # --- модель ----------------------------------------------------------- #

    @app.post("/api/models/download")
    def api_models_download():
        with _model_job_lock:
            if _model_job["state"] == "working":
                return jsonify({"started": False, "message": "Уже скачивается"}), 200
        threading.Thread(target=_run_model_download, daemon=True).start()
        return jsonify({"started": True})

    @app.get("/api/models/status")
    def api_models_status():
        return jsonify(dict(_model_job))

    # --- клонирование голоса ---------------------------------------------- #

    threading.Thread(target=_clone_engine_worker, daemon=True).start()

    @app.get("/api/clone/engine")
    def api_clone_engine():
        if _clone_state["state"] != "ready":
            return jsonify({"state": "loading"})
        if _clone_engine is None:
            return jsonify({"state": "ready", "available": False,
                            "why_not": _clone_state.get("why_not", "Библиотека TTS недоступна")})
        return jsonify({
            "state": "ready",
            "available": _clone_engine.available,
            "needs_model": _clone_engine.needs_model,
            "why_not": _clone_engine.why_not,
            "languages": [{"code": k, "name": v} for k, v in LANGUAGES.items()],
        })

    @app.get("/api/clone/samples")
    def api_clone_samples():
        if _clone_state["state"] != "ready" or _clone_engine is None:
            return jsonify({"samples": []})
        return jsonify({"samples": _clone_engine.list_samples()})

    @app.post("/api/clone/samples")
    def api_clone_samples_upload():
        if _clone_state["state"] != "ready" or _clone_engine is None:
            return jsonify({"error": "Движок клонирования ещё не готов"}), 503
        file = request.files.get("file")
        if file is None:
            return jsonify({"error": "Файл с записью голоса не получен"}), 400
        name = (request.form.get("name") or "").strip()[:60] or "Мой голос"

        data = file.read()
        if len(data) > 25 * 1024 * 1024:
            return jsonify({"error": "Файл слишком большой (до 25 МБ)"}), 400

        # проверка, что это валидный WAV, и измерение длительности
        import io
        import wave

        try:
            with wave.open(io.BytesIO(data)) as w:
                seconds = w.getnframes() / float(w.getframerate() or 1)
        except Exception:
            return jsonify({"error": "Нужен WAV-файл. Интерфейс сам конвертирует "
                                      "запись/микрофон в WAV — загрузите файл через страницу."}), 400
        if seconds < 2:
            return jsonify({"error": f"Запись слишком короткая ({seconds:.1f} c). Нужно хотя бы 5–10 секунд."}), 400
        if seconds > 180:
            return jsonify({"error": "Запись слишком длинная. Лучше 10–30 секунд."}), 400

        slug = _slugify(name)
        folder = os.path.join(SAMPLES_DIR, slug)
        suffix = 2
        while os.path.isdir(folder):
            slug = f"{_slugify(name)}-{suffix}"
            suffix += 1
            folder = os.path.join(SAMPLES_DIR, slug)
        os.makedirs(folder, exist_ok=True)
        with open(os.path.join(folder, "sample.wav"), "wb") as fh:
            fh.write(data)
        meta = {"name": name, "seconds": round(seconds, 1), "ts": time.strftime("%Y-%m-%d %H:%M")}
        with open(os.path.join(folder, "meta.json"), "w", encoding="utf-8") as fh:
            json.dump(meta, fh, ensure_ascii=False)
        return jsonify({"ok": True, "slug": slug, **meta, "url": f"/samples/{slug}"})

    @app.delete("/api/clone/samples/<slug>")
    def api_clone_samples_delete(slug: str):
        import shutil

        folder = os.path.join(SAMPLES_DIR, _safe_filename(slug))
        if os.path.isdir(folder):
            shutil.rmtree(folder, ignore_errors=True)
        return jsonify({"ok": True})

    @app.get("/samples/<slug>")
    def sample_audio(slug: str):
        path = os.path.join(SAMPLES_DIR, _safe_filename(slug), "sample.wav")
        if not os.path.isfile(path):
            return jsonify({"error": "Образец не найден"}), 404
        return send_file(path, mimetype="audio/wav")

    @app.post("/api/clone/say")
    def api_clone_say():
        if _clone_state["state"] != "ready" or _clone_engine is None:
            return jsonify({"error": "Движок клонирования ещё не готов"}), 503
        if not _clone_engine.available:
            return jsonify({"error": f"Клонирование недоступно: {_clone_engine.why_not}"}), 400

        data = request.get_json(silent=True) or {}
        text = (data.get("text") or "").strip()
        slug = (data.get("voice") or "").strip()
        language = data.get("language", "ru")
        if not text:
            return jsonify({"error": "Введите текст"}), 400
        if len(text) > MAX_CLONE_TEXT_LEN:
            return jsonify({"error": f"Для клонирования максимум {MAX_CLONE_TEXT_LEN} символов за раз"}), 400
        if language not in LANGUAGES:
            return jsonify({"error": f"Неизвестный язык «{language}»"}), 400
        try:
            speed = float(data.get("speed", 1.0))
        except (TypeError, ValueError):
            return jsonify({"error": "Некорректная скорость"}), 400

        started = time.time()
        try:
            result = _clone_engine.synthesize(text, slug, speed=speed,
                                              options={"language": language})
        except EngineError as exc:
            return jsonify({"error": str(exc)}), 400
        except Exception as exc:
            log.exception("Ошибка клонирования")
            return jsonify({"error": f"Внутренняя ошибка: {exc}"}), 500
        synth_ms = int((time.time() - started) * 1000)

        os.makedirs(OUTPUT_DIR, exist_ok=True)
        voice_name = next((s.get("name", s["slug"]) for s in _clone_engine.list_samples()
                           if s["slug"] == slug), slug)
        stamp = time.strftime("%Y%m%d-%H%M%S")
        filename = _safe_filename(f"{stamp}_clone-{slug}.wav")
        with open(os.path.join(OUTPUT_DIR, filename), "wb") as fh:
            fh.write(result.audio)

        try:
            import wave as wavemod
            with wavemod.open(os.path.join(OUTPUT_DIR, filename), "rb") as w:
                seconds = round(w.getnframes() / w.getframerate(), 2)
        except Exception:
            seconds = None

        entry = {
            "file": filename,
            "url": f"/audio/{filename}",
            "text": text[:140] + ("…" if len(text) > 140 else ""),
            "engine": "xtts",
            "voice": slug,
            "voice_name": f"🎭 {voice_name}",
            "speed": speed,
            "seconds": seconds,
            "synth_ms": synth_ms,
            "ts": stamp,
        }
        _add_history(entry)
        return jsonify(entry)

    @app.post("/api/clone/download")
    def api_clone_download():
        if _clone_state["state"] != "ready" or _clone_engine is None:
            return jsonify({"started": False, "message": "Движок ещё не готов"}), 503
        with _clone_job_lock:
            if _clone_job["state"] == "working":
                return jsonify({"started": False, "message": "Уже скачивается"}), 200
        threading.Thread(target=_run_clone_model_download, daemon=True).start()
        return jsonify({"started": True})

    @app.get("/api/clone/status")
    def api_clone_status():
        return jsonify(dict(_clone_job))

    return app


# --------------------------------------------------------------------------- #
#  CLI                                                                         #
# --------------------------------------------------------------------------- #

def _cmd_say(args) -> int:
    engine: Optional[object]
    if args.voice and "/" in args.voice:
        engine_name, voice_id = args.voice.split("/", 1)
        engine = registry.get(engine_name)
    else:
        engine = registry.default()
        voice_id = args.voice or engine.voices()[0].id

    if not engine.available:
        print(f"Движок «{engine.title}» недоступен: {engine.why_not}")
        return 1

    result = engine.synthesize(args.text, voice_id, speed=args.speed,
                               sample_rate=args.sample_rate)
    out = args.out or f"speech_{engine.id}_{voice_id}.{result.ext}"
    with open(out, "wb") as fh:
        fh.write(result.audio)
    print(f"Готово: {out} ({len(result.audio) // 1024} КБ)")
    return 0


def _cmd_voices(_args) -> int:
    for engine in registry.engines:
        state = "✓" if engine.available else ("⬇ нет модели" if engine.needs_model else "✗")
        print(f"\n{state} {engine.title} [{engine.id}]")
        if not engine.available and not engine.needs_model:
            print(f"   причина: {engine.why_not}")
            continue
        try:
            for v in engine.voices():
                print(f"   {engine.id}/{v.id:<28} {v.gender or '—':<8} {v.description}")
        except Exception as exc:
            print(f"   не удалось получить список: {exc}")
    return 0


def _cmd_clone(args) -> int:
    engine = XTTSEngine()
    if not engine.available:
        print(f"Клонирование недоступно: {engine.why_not}")
        return 1
    samples = engine.list_samples()
    if not samples:
        print("Сначала загрузите образец голоса через веб-интерфейс (вкладка «Клонирование»).")
        return 1
    slug = args.voice or samples[0]["slug"]
    result = engine.synthesize(args.text, slug, speed=args.speed,
                               options={"language": args.lang})
    out = args.out or f"clone_{slug}.wav"
    with open(out, "wb") as fh:
        fh.write(result.audio)
    print(f"Готово: {out} ({len(result.audio) // 1024} КБ)")
    return 0


def _cmd_serve(args) -> int:
    app = create_app()
    silero = registry.get("silero")
    if silero.available:
        threading.Thread(target=silero.warmup, daemon=True).start()
    elif silero.needs_model:
        print("Нейромодель не найдена. Скачайте её: python app.py download-models")
    print(f"\nОткройте в браузере: http://{args.host if args.host != '0.0.0.0' else '127.0.0.1'}:{args.port}\n")
    app.run(host=args.host, port=args.port, threaded=True)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="app.py",
        description="Голосовой ИИ: приложение для синтеза речи (озвучки текста).",
    )
    sub = parser.add_subparsers(dest="command")

    p_serve = sub.add_parser("serve", help="запустить веб-интерфейс")
    p_serve.add_argument("--host", default="0.0.0.0")
    p_serve.add_argument("--port", type=int, default=8000)
    p_serve.set_defaults(func=_cmd_serve)

    p_say = sub.add_parser("say", help="озвучить текст в файл")
    p_say.add_argument("text", help="текст для озвучки")
    p_say.add_argument("--voice", help="голос: silero/kseniya, edge/ru-RU-SvetlanaNeural …")
    p_say.add_argument("--speed", type=float, default=1.0, help="скорость 0.5–2.0")
    p_say.add_argument("--sample-rate", type=int, default=48000, choices=[24000, 48000])
    p_say.add_argument("--out", help="имя выходного файла")
    p_say.set_defaults(func=_cmd_say)

    p_voices = sub.add_parser("voices", help="показать доступные голоса")
    p_voices.set_defaults(func=_cmd_voices)

    p_dl = sub.add_parser("download-models", help="скачать нейромодель")
    p_dl.set_defaults(func=lambda _a: __import__("voiceai.download_models", fromlist=["main"]).main())

    p_clone = sub.add_parser("clone", help="озвучить текст склонированным голосом")
    p_clone.add_argument("text", help="текст для озвучки")
    p_clone.add_argument("--voice", help="образец голоса (см. список в веб-интерфейсе)")
    p_clone.add_argument("--lang", default="ru", choices=list(LANGUAGES))
    p_clone.add_argument("--speed", type=float, default=1.0)
    p_clone.add_argument("--out", help="имя выходного файла")
    p_clone.set_defaults(func=_cmd_clone)

    p_dlc = sub.add_parser("download-clone-model", help="скачать модель клонирования (~1.9 ГБ)")
    p_dlc.set_defaults(func=lambda _a: __import__("voiceai.download_clone_model", fromlist=["main"]).main())

    args = parser.parse_args()
    if not getattr(args, "command", None):
        parser.print_help()
        print("\nПодсказка: попробуйте «python app.py serve»")
        return 0
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
