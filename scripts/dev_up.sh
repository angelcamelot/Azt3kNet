#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")"/.. && pwd)"
ENV_FILE="$ROOT_DIR/infra/docker/.env"
COMPOSE_FILE="$ROOT_DIR/docker-compose.yml"

if [[ ! -f "$ENV_FILE" ]]; then
  echo "[dev_up] Missing infra/docker/.env. Run scripts/bootstrap_env.sh first." >&2
  exit 1
fi

if [[ ! -f "$ROOT_DIR/.env" ]]; then
  echo "[dev_up] Missing .env. Run scripts/bootstrap_env.sh first." >&2
  exit 1
fi

docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" up -d "$@"
