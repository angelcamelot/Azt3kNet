#!/usr/bin/env bash
# Bootstrap the Mailcow Dockerized stack next to the Azt3kNet project.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# Resolve the repository root by travelling three directories up from the
# bootstrap script location (infra/docker/mailcow). This keeps the script
# functional regardless of the working directory from which it is invoked.
ROOT_DIR="$(cd "${SCRIPT_DIR}/../../.." && pwd)"
MAILCOW_DIR="$ROOT_DIR/infra/docker/mailcow/mailcow-dockerized"
DOMAIN="${DESEC_DOMAIN:-${AZT3KNET_DOMAIN:-azt3knet.dedyn.io}}"
MAIL_HOST="mail.${DOMAIN}"

if [[ ! -d "$MAILCOW_DIR" ]]; then
  echo "Cloning mailcow/mailcow-dockerized into $MAILCOW_DIR" >&2
  git clone https://github.com/mailcow/mailcow-dockerized "$MAILCOW_DIR"
else
  echo "Reusing existing mailcow-dockerized checkout" >&2
fi

cd "$MAILCOW_DIR"

if [[ ! -f mailcow.conf ]]; then
  echo "Generating Mailcow configuration for $MAIL_HOST" >&2
  MAILCOW_HOSTNAME="$MAIL_HOST" ./generate_config.sh </dev/null
else
  echo "mailcow.conf already present; skipping configuration generation" >&2
fi

echo "Writing wrapper docker-compose file" >&2
cat >"$ROOT_DIR/infra/docker/mailcow/docker-compose.mailcow.yml" <<COMPOSE
version: "3.9"

# Thin wrapper that requires Docker Compose v2.20 or newer with 'include' support.
include:
  - ./mailcow-dockerized/docker-compose.yml
COMPOSE

echo "Mailcow bootstrap completed. Start the stack with:" >&2
echo "  docker compose -f infra/docker/mailcow/docker-compose.mailcow.yml up -d" >&2
