#!/usr/bin/env bash
# Double-click this file in Finder to start ping-me-when.
# It will:
#   1. cd to this script's directory
#   2. ensure a .venv exists (creating it on first run)
#   3. install requirements if not yet installed
#   4. launch the local web server and open your browser

set -e
cd "$(dirname "$0")"

PYTHON_BIN="${PYTHON_BIN:-python3}"

if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  echo "Python 3 is required but was not found."
  echo "Install it from https://www.python.org/downloads/ and try again."
  echo "Press any key to close this window."
  read -n 1
  exit 1
fi

if [ ! -d ".venv" ]; then
  echo "First-time setup: creating Python environment (this takes ~30 seconds)..."
  "$PYTHON_BIN" -m venv .venv
fi

source .venv/bin/activate
python -m pip install --quiet --upgrade pip
python -m pip install --quiet -r requirements.txt

echo ""
echo "Starting ping-me-when. Your browser will open at http://127.0.0.1:8765/"
echo "To stop, close this window or run stop.command."
echo ""

# Write our pid so stop.command can target it precisely instead of doing a
# fuzzy `pkill -f`.
echo $$ > .ping-me-when.pid
trap 'rm -f .ping-me-when.pid' EXIT
exec python -m src.server
