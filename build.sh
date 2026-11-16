#!/usr/bin/env bash
set -euo pipefail
python -m pip install -r requirements.txt
python manage.py collectstatic --noinput
if [ -n "${DATABASE_URL_UNPOOLED:-}" ]; then
    python manage.py migrate --database=migration --noinput
else
    python manage.py migrate --noinput
fi
