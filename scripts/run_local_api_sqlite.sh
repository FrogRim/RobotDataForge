#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

export DATABASE_URL="${DATABASE_URL:-sqlite:///./storage/local_api.sqlite}"
export STORAGE_ROOT="${STORAGE_ROOT:-storage}"

uv run python scripts/init_local_db.py
exec uv run uvicorn app.main:app --app-dir apps/api --reload
