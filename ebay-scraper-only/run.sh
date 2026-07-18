#!/usr/bin/env bash
# One-shot launcher: creates a local virtual environment on first run,
# installs dependencies into it, and runs the scraper. Safe to re-run -
# it skips setup steps that are already done.

set -e
cd "$(dirname "$0")"

if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

echo "Installing dependencies..."
./venv/bin/pip install --quiet --upgrade pip
./venv/bin/pip install --quiet -r requirements.txt

if [ ! -f ".env" ]; then
    echo ""
    echo "No .env file found - creating one from .env.example."
    cp .env.example .env
    echo "Edit .env and add your eBay Client ID / Secret, then run this script again."
    exit 1
fi

echo "Running scraper..."
./venv/bin/python ebay_scrape.py
