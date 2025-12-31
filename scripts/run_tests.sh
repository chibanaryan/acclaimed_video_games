#!/bin/bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if [[ -x "venv/bin/python" ]]; then
    PYTHON_BIN="venv/bin/python"
else
    PYTHON_BIN="python"
fi

export DATABASE_URL="${DATABASE_URL:-sqlite:///db.sqlite3}"
export CACHE_URL="${CACHE_URL:-locmemcache://}"
export CORS_ALLOWED_ORIGINS="${CORS_ALLOWED_ORIGINS:-http://localhost}"

echo "Running Django tests via pre-commit..."
"$PYTHON_BIN" manage.py test games.tests --parallel auto
