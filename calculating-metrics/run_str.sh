#!/usr/bin/env bash
# Launcher for str_calculator.py - reuses the same venv as run.sh.

set -e
cd "$(dirname "$0")"

if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

echo "Installing dependencies..."
./venv/bin/pip install --quiet --upgrade pip
./venv/bin/pip install --quiet -r requirements.txt
./venv/bin/python -m playwright install chromium

if [ ! -f ".env" ]; then
    echo ""
    echo "No .env file found - creating one from .env.example."
    cp .env.example .env
    echo "Edit .env and add your eBay Client ID / Secret, then run this script again."
    exit 1
fi

echo "Running STR calculator..."
./venv/bin/python str_calculator.py
