@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo ============================================
echo   Голосовой ИИ — запуск...
echo ============================================

where python >nul 2>nul
if errorlevel 1 (
  echo [!] Python не найден. Установите его с https://python.org
  echo     и при установке поставьте галочку "Add Python to PATH".
  pause
  exit /b 1
)

if not exist .venv\Scripts\python.exe (
  echo [1/3] Создаю виртуальное окружение...
  python -m venv .venv || goto :err
)

echo [2/3] Проверяю зависимости (первый запуск может занять пару минут)...
.venv\Scripts\python -m pip install --quiet --disable-pip-version-check -r requirements.txt || goto :err

echo [3/3] Запускаю веб-интерфейс...
echo.
echo   Откройте в браузере:  http://127.0.0.1:8000
echo   Для остановки закройте это окно.
echo.
.venv\Scripts\python app.py serve --host 127.0.0.1 --port 8000
pause
exit /b

:err
echo.
echo [!] Не удалось запустить приложение. Проверьте установку Python и интернет.
pause
