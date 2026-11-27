@echo off
chcp 65001 >nul
cd /d "%~dp0"

REM Создаём отдельное окружение проекта, если его ещё нет.
if not exist ".venv\Scripts\python.exe" (
    py -3 -m venv .venv
)

REM Устанавливаем Flask и запускаем сайт.
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe app.py
pause
