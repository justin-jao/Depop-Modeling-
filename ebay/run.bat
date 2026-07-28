@echo off
REM One-shot launcher: creates a local virtual environment on first run,
REM installs dependencies into it, and runs the scraper. Safe to re-run -
REM it skips setup steps that are already done.

cd /d "%~dp0"

if not exist venv (
    echo Creating virtual environment...
    python -m venv venv
)

echo Installing dependencies...
venv\Scripts\pip install --quiet --upgrade pip
venv\Scripts\pip install --quiet -r requirements.txt

if not exist .env (
    echo.
    echo No .env file found - creating one from .env.example.
    copy .env.example .env
    echo Edit .env and add your eBay Client ID / Secret, then run this script again.
    exit /b 1
)

echo Running scraper...
venv\Scripts\python ebay_scrape.py
pause
