@echo off
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo Creating virtual environment...
    py -3 -m venv .venv
    if errorlevel 1 (
        echo Python 3 is required. Install it from https://www.python.org and try again.
        pause
        exit /b 1
    )
)

".venv\Scripts\python.exe" -m pip install -r requirements.txt

echo.
echo Starting the site: http://127.0.0.1:5000
".venv\Scripts\python.exe" app.py
pause
