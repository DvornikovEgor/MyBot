#!/usr/bin/env python3
"""Веб-интерфейс для локального ИИ-собеседника.

Запуск:
    python3 server.py [порт]

По умолчанию бот доступен на http://127.0.0.1:8080 (или на 0.0.0.0:8080,
когда сервер запускается в песочнице Arena).

Использует только стандартную библиотеку Python.
"""

from __future__ import annotations

import json
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from bot import ChatBot

# Пути.
ROOT = Path(__file__).resolve().parent
INDEX = ROOT / "index.html"

#: Один инстанс бота на весь сервер (защищён блокировкой).
_bot = ChatBot()


class RequestHandler(BaseHTTPRequestHandler):
    """Обработчик HTTP-запросов."""

    server_version = "MyBot/1.0"

    # -- ответы --------------------------------------------------------------

    def _send(self, code: int, body: bytes, content_type: str) -> None:
        try:
            self.send_response(code)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            # Клиент закрыл соединение — для сервера это не ошибка.
            pass

    def _json(self, data: dict, code: int = 200) -> None:
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self._send(code, body, "application/json; charset=utf-8")

    def _page(self) -> None:
        try:
            content = INDEX.read_bytes()
        except OSError:
            content = (
                "<html><head><meta charset='utf-8'></head><body>"
                "<h3>index.html не найден</h3>"
                "<p>Запусти сервер из папки проекта.</p>"
                "</body></html>"
            ).encode("utf-8")
        self._send(200, content, "text/html; charset=utf-8")

    # -- маршруты --------------------------------------------------------------

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path in ("/", "/index.html"):
            self._page()
            return
        if path == "/api/state":
            self._json({"state": _bot.state()})
            return
        if path == "/favicon.ico":
            self._send(204, b"", "image/x-icon")
            return
        self._json({"error": "not_found"}, 404)

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        if path == "/api/chat":
            self._chat()
            return
        if path == "/api/reset":
            self._reset()
            return
        self._json({"error": "not_found"}, 404)

    def log_message(self, format_str: str, *args) -> None:
        """Тихий режим: выводим только содержательные сообщения."""
        timestamp = self.log_date_time_string()
        print(f"{timestamp} - {format_str % args}")

    # -- логика -----------------------------------------------------------------

    def _read_json(self) -> dict:
        """Читает JSON из тела запроса. Никогда не бросает исключений."""
        try:
            length = int(self.headers.get("Content-Length", "0") or "0")
        except (TypeError, ValueError):
            length = 0
        if length <= 0 or length > 100_000:
            return {}
        try:
            raw = self.rfile.read(length)
            if not raw:
                return {}
            data = json.loads(raw.decode("utf-8"))
            return data if isinstance(data, dict) else {}
        except (ValueError, UnicodeDecodeError):
            return {}

    def _chat(self) -> None:
        data = self._read_json()
        message = data.get("message")
        if not isinstance(message, str):
            message = ""
        reply = _bot_reply(message)
        self._json({"reply": reply, "state": _bot.state()})

    def _reset(self) -> None:
        _bot.reset()
        self._json({"ok": True, "state": _bot.state()})


def _bot_reply(message: str) -> str:
    """Вызывает бота и гарантирует строку."""
    try:
        reply = _bot.reply(message)
        if not isinstance(reply, str) or not reply.strip():
            return "Что-то пошло не так, но я не сломался. Попробуй ещё раз!"
        return reply.strip()
    except Exception:  # сохраняем работоспособность сервера при любом сбое
        return "Произошла внутренняя ошибка, но я на связи. Задай вопрос иначе!"


def main() -> None:
    default_port = 8080
    port = default_port
    if len(sys.argv) > 1:
        try:
            port = int(sys.argv[1])
        except ValueError:
            print(f"Некорректный порт, использую {default_port}")

    host = os.environ.get("MYBOT_HOST", "0.0.0.0")

    try:
        server = ThreadingHTTPServer((host, port), RequestHandler)
    except OSError as exc:
        print(f"Не удалось запустить сервер на {host}:{port}: {exc}")
        raise SystemExit(1) from exc

    print("=" * 60)
    print("  MyBot — локальный ИИ без API и без ошибок")
    print(f"  Открой в браузере:  http://{host}:{port}")
    print("  Останови сервер:    Ctrl+C")
    print("=" * 60)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nОстанавливаю сервер...")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
