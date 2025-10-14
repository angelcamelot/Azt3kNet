#!/usr/bin/env bash
set -euo pipefail

if [[ "${POSTGRES_ENABLE_TIMESCALEDB:-false}" != "true" ]]; then
  echo "[initdb] POSTGRES_ENABLE_TIMESCALEDB is not true; skipping TimescaleDB extension." >&2
  exit 0
fi

if ! command -v psql >/dev/null 2>&1; then
  echo "[initdb] psql not found; cannot enable TimescaleDB." >&2
  exit 0
fi

psql -v ON_ERROR_STOP=1 --username "${POSTGRES_USER}" --dbname "${POSTGRES_DB}" <<'SQL'
CREATE EXTENSION IF NOT EXISTS timescaledb;
SQL
