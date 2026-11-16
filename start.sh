#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
PAMOJA_PYTHON=""
for candidate in python3.13 python3.14 python3.12 python3.11 python3.10 python3; do
  if command -v "$candidate" >/dev/null 2>&1 && "$candidate" -c 'import sys; raise SystemExit(not ((3, 10) <= sys.version_info[:2] < (3, 15)))'; then
    PAMOJA_PYTHON="$candidate"
    break
  fi
done
if [ -z "$PAMOJA_PYTHON" ]; then
  echo "PAMOJA needs Python 3.10–3.14. Install Python 3.13 from python.org, then run bash start.sh again."
  exit 1
fi
if [ ! -d .venv ]; then
  "$PAMOJA_PYTHON" -m venv .venv
fi
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python manage.py migrate
echo ""
echo "PAMOJA is ready. Open http://127.0.0.1:8000/ in your browser."
echo "Press Control+C to stop the server."
.venv/bin/python manage.py runserver 127.0.0.1:8000
