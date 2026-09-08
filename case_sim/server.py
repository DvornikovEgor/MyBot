#!/usr/bin/env python3
"""Мини-сервер симулятора кейсов (нужен только для предпросмотра).

Обычно сервер не нужен: просто откройте index.html двойным кликом в браузере.

Запуск:  python case_sim/server.py   →  http://127.0.0.1:8010
"""

import os

from flask import Flask, send_from_directory

BASE = os.path.dirname(os.path.abspath(__file__))
app = Flask(__name__, static_folder=None)


@app.route("/")
def index():
    return send_from_directory(BASE, "index.html")


if __name__ == "__main__":
    print("Симулятор кейсов: откройте http://127.0.0.1:8010")
    app.run(host="0.0.0.0", port=8010, threaded=True)
