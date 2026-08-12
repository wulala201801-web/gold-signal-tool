#!/bin/bash
cd "$(dirname "$0")"
if ! curl -fsS --max-time 2 http://127.0.0.1:8765/ >/dev/null 2>&1; then
  python3 server.py > /tmp/gold-signal-tool.log 2>&1 &
  sleep 1
fi
open "http://127.0.0.1:8765"
