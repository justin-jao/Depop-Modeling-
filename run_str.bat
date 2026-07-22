@echo off
REM Launcher for str_calculator.py - reuses the same venv as run.bat.

cd /d "%~dp0"

if not exist venv (
    echo Creating virtual environment...
    python -m venv venv
)

echo Installing dependencies...
venv\Scripts\pip install --quiet --upgrade pip
venv\Scripts\pip install --quiet -r requirements.txt
venv\Scripts\python -m playwright install chromium

if not exist .env (
    echo.
    echo No .env file found - creating one from .env.example.
    copy .env.example .env
    echo Edit .env and add your eBay Client ID / Secret, then run this script again.
    exit /b 1
)

echo Running STR calculator...
venv\Scripts\python str_calculator.py
pause
