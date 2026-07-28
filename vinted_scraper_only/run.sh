#!/usr/bin/env bash
# One-shot launcher: creates a local virtual environment on first run,
# installs dependencies into it, installs Playwright Chromium, and runs
# the Vinted scraper. Safe to re-run.

set -euo pipefail
cd "$(dirname "$0")"

if ! command -v python3 >/dev/null 2>&1; then
    echo "python3 is required but was not found on PATH."
    exit 1
fi

if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

echo "Installing dependencies..."
./venv/bin/python -m pip install --quiet --upgrade pip
./venv/bin/python -m pip install --quiet -r requirements.txt
./venv/bin/python -m playwright install chromium

echo "Running Vinted scraper..."
exec ./venv/bin/python vinted_scraper.py
