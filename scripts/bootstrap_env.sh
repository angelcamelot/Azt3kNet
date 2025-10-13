#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")"/.. && pwd)"
ENV_FILE="$ROOT_DIR/.env"

if [[ -f "$ENV_FILE" ]]; then
  echo "[bootstrap_env] .env already exists. Skipping copy." >&2
else
  cp "$ROOT_DIR/.env.example" "$ENV_FILE"
  echo "[bootstrap_env] Created .env from .env.example" >&2
fi

if [[ -f "$ROOT_DIR/infra/docker/.env" ]]; then
  echo "[bootstrap_env] infra/docker/.env already exists. Skipping copy." >&2
else
  cp "$ROOT_DIR/infra/docker/.env.example" "$ROOT_DIR/infra/docker/.env"
  echo "[bootstrap_env] Created infra/docker/.env from template" >&2
fi
