@echo off
REM Double-click this file to start ping-me-when on Windows.
cd /d "%~dp0"

where python >nul 2>nul
if errorlevel 1 (
    echo Python 3 is required but was not found.
    echo Install it from https://www.python.org/downloads/ then try again.
    pause
    exit /b 1
)

if not exist ".venv" (
    echo First-time setup: creating Python environment...
    python -m venv .venv
)

call .venv\Scripts\activate
python -m pip install --quiet --upgrade pip
python -m pip install --quiet -r requirements.txt

echo.
echo Starting ping-me-when. Your browser will open at http://127.0.0.1:8765/
echo To stop, close this window.
echo.
python -m src.server
