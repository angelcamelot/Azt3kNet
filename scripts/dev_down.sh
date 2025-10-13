#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")"/.. && pwd)"
ENV_FILE="$ROOT_DIR/infra/docker/.env"
COMPOSE_FILE="$ROOT_DIR/docker-compose.yml"

docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" down "$@"
