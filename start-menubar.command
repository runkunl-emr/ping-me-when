#!/usr/bin/env bash
# Launch ping-me-when as a macOS menu-bar app instead of a terminal-bound server.
# After first run, you'll see a 📨 icon in the menu bar (top right).
# Click it for status / start / stop / open settings.

set -e
cd "$(dirname "$0")"

PYTHON_BIN="${PYTHON_BIN:-python3}"

if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  echo "Python 3 is required but was not found."
  echo "Install it from https://www.python.org/downloads/ and try again."
  read -n 1 -s -r -p "Press any key to close..."
  exit 1
fi

if [ ! -d ".venv" ]; then
  echo "First-time setup: creating Python environment (~30 seconds)..."
  "$PYTHON_BIN" -m venv .venv
fi

source .venv/bin/activate
python -m pip install --quiet --upgrade pip
python -m pip install --quiet -r requirements.txt

echo ""
echo "Starting ping-me-when in the menu bar."
echo "Look for the 📨 icon at the top of your screen."
echo ""

echo $$ > .ping-me-when.pid
trap 'rm -f .ping-me-when.pid' EXIT
exec python -m src.menubar
