#!/usr/bin/env bash
# Голосовой ИИ — запуск (Linux / macOS)
set -e
cd "$(dirname "$0")"

echo "============================================"
echo "  Голосовой ИИ — запуск..."
echo "============================================"

if ! command -v python3 >/dev/null 2>&1; then
  echo "[!] Python не найден. Установите: sudo apt install python3 python3-venv"
  exit 1
fi

if [ ! -x .venv/bin/python ]; then
  echo "[1/3] Создаю виртуальное окружение..."
  python3 -m venv .venv
fi

echo "[2/3] Проверяю зависимости (первый запуск может занять пару минут)..."
.venv/bin/python -m pip install --quiet --disable-pip-version-check -r requirements.txt

echo "[3/3] Запускаю веб-интерфейс..."
echo
echo "  Откройте в браузере:  http://127.0.0.1:8000"
echo "  Для остановки нажмите Ctrl+C"
echo
exec .venv/bin/python app.py serve --host 127.0.0.1 --port 8000
