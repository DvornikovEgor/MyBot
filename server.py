#!/usr/bin/env python3
"""
MyBot · генератор музыки — static server + AI director proxy.

Serves the app and exposes two JSON endpoints:

    GET  /api/health  → is the AI (Gemini) configured?
    POST /api/chat    → one turn of conversation → a music recipe

The Gemini API key never leaves this process: the browser talks to /api/* only.
Run with the key in the environment:

    GEMINI_API_KEY=... python3 server.py
"""

import json
import os
import socketserver
import sys
import urllib.parse
from http.server import SimpleHTTPRequestHandler
from http.server import ThreadingHTTPServer

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import ai  # noqa: E402

PORT = int(os.environ.get("PORT", 8000))
HOST = os.environ.get("HOST", "0.0.0.0")
ROOT = os.path.dirname(os.path.abspath(__file__))
MAX_BODY = 256 * 1024


class Handler(SimpleHTTPRequestHandler):
    extensions_map = {
        **SimpleHTTPRequestHandler.extensions_map,
        ".js": "text/javascript",
        ".mjs": "text/javascript",
        ".css": "text/css",
        ".json": "application/json",
        ".wav": "audio/wav",
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=ROOT, **kwargs)

    # ---- plumbing --------------------------------------------------------

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def log_message(self, fmt, *args):  # quieter console
        if os.environ.get("MYBOT_VERBOSE"):
            super().log_message(fmt, *args)

    def _send_json(self, status, payload):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        try:
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def _send_error_json(self, status, code, message):
        self._send_json(status, {"ok": False, "error": {"code": code, "message": message}})

    # ---- routes ----------------------------------------------------------

    def do_GET(self):
        path = urllib.parse.urlparse(self.path).path
        if path == "/api/health":
            return self._send_json(200, {"ok": True, "ai": ai.health()})
        if path == "/api/config":
            # Same as /health, kept as an alias for convenience.
            return self._send_json(200, {"ok": True, "ai": ai.health()})
        if path.startswith("/api/"):
            return self._send_error_json(404, "not_found", "Неизвестный API-маршрут.")
        if path == "/":
            path = "/index.html"
        return super().do_GET()

    def do_POST(self):
        path = urllib.parse.urlparse(self.path).path
        if path != "/api/chat":
            return self._send_error_json(404, "not_found", "Неизвестный API-маршрут.")

        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            length = 0
        if length <= 0:
            return self._send_error_json(400, "empty_body", "Пустое тело запроса.")
        if length > MAX_BODY:
            return self._send_error_json(413, "too_large", "Слишком большой запрос.")

        try:
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            return self._send_error_json(400, "bad_json", "Тело запроса должно быть JSON.")

        messages = _clean_messages(payload.get("messages"))
        if not messages:
            return self._send_error_json(400, "no_message", "Нет ни одного сообщения.")

        current = payload.get("current") if isinstance(payload.get("current"), dict) else None
        try:
            result = ai.chat(messages, current, ai.Config())
        except ai.DirectorError as exc:
            return self._send_error_json(exc.status, exc.code, exc.message)
        except Exception as exc:  # noqa: BLE001 - never leak a stack trace to the UI
            print(f"[mybot] AI failure: {exc!r}", file=sys.stderr)
            return self._send_error_json(502, "internal", "Внутренняя ошибка ИИ-модуля.")

        return self._send_json(200, {"ok": True, **result})


def _clean_messages(messages) -> list[dict[str, str]]:
    """Accept only well-formed, non-empty user/model turns."""
    if not isinstance(messages, list):
        return []
    out = []
    for msg in messages:
        if not isinstance(msg, dict):
            continue
        role = msg.get("role")
        text = msg.get("text")
        if role not in ("user", "model") or not isinstance(text, str):
            continue
        text = text.strip()
        if not text or len(text) > 4000:
            continue
        out.append({"role": role, "text": text})
    return out


def main():
    socketserver.TCPServer.allow_reuse_address = True
    config = ai.Config()
    with ThreadingHTTPServer((HOST, PORT), Handler) as httpd:
        banner = ai.health(config)
        print(f"MyBot · генератор музыки → http://{HOST}:{PORT}")
        if banner["ready"]:
            print(f"AI-дирижёр: {banner['provider']} · модель {banner['model']}")
        else:
            print("AI-дирижёр выключен: не задан GEMINI_API_KEY (см. README).")
        if os.environ.get("MYBOT_AI_FAKE"):
            print("ВНИМАНИЕ: MYBOT_AI_FAKE=1 — ответы идут из локальной заглушки, не из Gemini.")
        httpd.serve_forever()


if __name__ == "__main__":
    main()
