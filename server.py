#!/usr/bin/env python3
"""MyBot server — static + optional AI proxy (настоящий ИИ)."""
import http.server
import json
import os
import socketserver
import urllib.request
import urllib.error

PORT = int(os.environ.get("PORT", 8000))
ROOT = os.path.dirname(os.path.abspath(__file__))


class Handler(http.server.SimpleHTTPRequestHandler):
    extensions_map = {
        **http.server.SimpleHTTPRequestHandler.extensions_map,
        ".js": "text/javascript",
        ".mjs": "text/javascript",
        ".css": "text/css",
        ".json": "application/json",
        ".wav": "audio/wav",
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=ROOT, **kwargs)

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        # CORS для AI
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(204)
        self.end_headers()

    def do_POST(self):
        if self.path == "/api/chat":
            self.handle_chat()
        else:
            self.send_error(404, "Not found")

    def handle_chat(self):
        # Читаем тело
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length) if length else b"{}"
        try:
            data = json.loads(raw.decode("utf-8") or "{}")
        except:
            data = {}
        messages = data.get("messages") or [{"role":"user","content": data.get("prompt","Привет")}]
        model = data.get("model", "mybot-pro")
        api_key = self.headers.get("Authorization", "").replace("Bearer ","") or os.environ.get("OPENAI_API_KEY", "") or data.get("api_key","")

        # Если есть ключ — проксируем в выбранный API
        if api_key:
            try:
                # выбираем base_url по провайдеру
                provider = data.get("model","openai")
                base_map = {
                    "openai": "https://api.openai.com/v1/chat/completions",
                    "groq": "https://api.groq.com/openai/v1/chat/completions",
                    "openrouter": "https://openrouter.ai/api/v1/chat/completions",
                }
                base_url = os.environ.get("OPENAI_BASE_URL") or base_map.get(provider, base_map["openai"])
                payload = json.dumps({
                    "model": data.get("openai_model","gpt-4o-mini"),
                    "messages": messages,
                    "temperature": data.get("temperature", 0.8),
                    "max_tokens": 2000
                }).encode()
                req = urllib.request.Request(
                    base_url,
                    data=payload,
                    headers={"Content-Type":"application/json","Authorization": f"Bearer {api_key}"},
                    method="POST"
                )
                with urllib.request.urlopen(req, timeout=20) as resp:
                    body = resp.read()
                    self.send_response(200)
                    self.send_header("Content-Type","application/json")
                    self.end_headers()
                    self.wfile.write(body)
                    return
            except Exception as e:
                err = {"error": f"OpenAI proxy failed: {e}", "fallback": True}
                # упадём в fallback — вернём демо-ответ
                self.send_response(200)
                self.send_header("Content-Type","application/json")
                self.end_headers()
                # Простой локальный fallback ответ (клиент и так умеет офлайн, но дадим что-то)
                fallback_text = "Привет! Я MyBot AI (серверный fallback). Твой запрос получен, но внешний API недоступен — я работаю в офлайн-режиме прямо в браузере. Задай вопрос снова — отвечу локально без ключа."
                self.wfile.write(json.dumps({"choices":[{"message":{"role":"assistant","content":fallback_text}}],"fallback":True}).encode())
                return
        else:
            # Нет ключа — говорим клиенту использовать локальный движок
            self.send_response(200)
            self.send_header("Content-Type","application/json")
            self.end_headers()
            msg = "Локальный MyBot AI активен. Отправь запрос без ключа — всё работает офлайн в браузере. Если хочешь облачный GPT, передай Authorization: Bearer <ключ>."
            self.wfile.write(json.dumps({"choices":[{"message":{"role":"assistant","content":msg}}],"offline":True}).encode())


socketserver.TCPServer.allow_reuse_address = True

if __name__ == "__main__":
    with socketserver.TCPServer(("0.0.0.0", PORT), Handler) as httpd:
        print(f"MyBot AI + Music → http://0.0.0.0:{PORT}  (AI вкладка по умолчанию)")
        print(f"  /api/chat — POST для прокси к OpenAI (нужен Authorization Bearer <key>)")
        httpd.serve_forever()
