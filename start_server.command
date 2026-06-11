#!/bin/zsh
cd "$(dirname "$0")"
if lsof -nP -iTCP:8765 -sTCP:LISTEN >/dev/null 2>&1; then
  open "http://127.0.0.1:8765/"
  exit 0
fi
(sleep 1; open "http://127.0.0.1:8765/") &
python3 server.py --host 127.0.0.1 --port 8765
