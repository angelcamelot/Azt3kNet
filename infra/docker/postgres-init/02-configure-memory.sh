#!/usr/bin/env bash
set -euo pipefail

# docker-entrypoint-initdb.d scripts run only on first boot of a new data directory.
# Append tuning parameters when requested.
if [[ -z "${POSTGRES_SHARED_BUFFERS:-}" && -z "${TIMESCALEDB_MAX_MEMORY:-}" ]]; then
  exit 0
fi

CONF_FILE="${PGDATA}/postgresql.conf"
{
  echo ""
  echo "# Custom settings injected during init"
  if [[ -n "${POSTGRES_SHARED_BUFFERS:-}" ]]; then
    echo "shared_buffers = '${POSTGRES_SHARED_BUFFERS}'"
  fi
  if [[ "${POSTGRES_ENABLE_TIMESCALEDB:-false}" == "true" && -n "${TIMESCALEDB_MAX_MEMORY:-}" ]]; then
    echo "timescaledb.max_memory = '${TIMESCALEDB_MAX_MEMORY}'"
  fi
} >> "$CONF_FILE"
