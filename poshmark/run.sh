#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$SCRIPT_DIR/venv"
PYTHON_BIN="$VENV_DIR/bin/python"

if [[ ! -x "$PYTHON_BIN" ]]; then
  echo "Creating virtual environment..."
  python3 -m venv "$VENV_DIR"
fi

# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"

echo "Installing dependencies..."
pip install --upgrade pip >/dev/null
pip install playwright >/dev/null
python -m playwright install chromium >/dev/null

echo "Running Poshmark scraper..."
exec "$PYTHON_BIN" "$SCRIPT_DIR/poshmark-scraper" "$@"
