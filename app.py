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
from voiceai.registry import Registry

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
WEBUI_DIR = os.path.join(BASE_DIR, "webui")
OUTPUT_DIR = os.path.join(BASE_DIR, "outputs")
MANIFEST = os.path.join(OUTPUT_DIR, "manifest.json")
MAX_TEXT_LEN = 2000
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

    args = parser.parse_args()
    if not getattr(args, "command", None):
        parser.print_help()
        print("\nПодсказка: попробуйте «python app.py serve»")
        return 0
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
