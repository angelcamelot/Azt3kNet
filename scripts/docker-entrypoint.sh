#!/usr/bin/env bash
# Entrypoint for Docker containers running the Azt3kNet API.
#
# The script optionally bootstraps the Mailcow stack so that developers do not
# have to run `infra/docker/mailcow/bootstrap.sh` manually when working with the
# Docker Compose environment. The logic is idempotent and respects the
# AZT3KNET_AUTO_BOOTSTRAP_MAILCOW flag to allow opting out during production
# deployments where Mailcow may be provisioned externally.

set -euo pipefail

main() {
  if [[ "${AZT3KNET_AUTO_BOOTSTRAP_MAILCOW:-1}" == "1" ]]; then
    bootstrap_mailcow
  fi

  exec "$@"
}

bootstrap_mailcow() {
  local mailcow_root="/app/infra/docker/mailcow"
  local checkout_dir="${mailcow_root}/mailcow-dockerized"

  if [[ -d "${checkout_dir}" && -f "${checkout_dir}/mailcow.conf" ]]; then
    return
  fi

  if ! command -v git >/dev/null 2>&1; then
    echo "[mailcow] git is required for automatic bootstrap." >&2
    return
  fi

  echo "[mailcow] Bootstrapping Mailcow assets..." >&2
  if ! bash "${mailcow_root}/bootstrap.sh"; then
    echo "[mailcow] Automatic bootstrap failed; continuing without Mailcow." >&2
  else
    echo "[mailcow] Bootstrap completed." >&2
  fi
}

main "$@"
