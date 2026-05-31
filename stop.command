#!/usr/bin/env bash
# Double-click to stop ping-me-when.
cd "$(dirname "$0")"

PID_FILE=".ping-me-when.pid"

if [ -f "$PID_FILE" ]; then
  PID=$(cat "$PID_FILE")
  # Send SIGTERM so the listener gets a chance to close the WebSocket cleanly.
  kill -TERM "$PID" 2>/dev/null && echo "Sent stop signal to PID $PID"
  rm -f "$PID_FILE"
else
  # Fallback: kill anything running our server module.
  pkill -f "src.server" 2>/dev/null && echo "Stopped (best-effort)"
fi

sleep 0.5
echo "Done."
