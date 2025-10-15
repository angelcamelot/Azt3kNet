#!/usr/bin/env bash
# Bootstrap script executed when the Azt3kNet container starts.

set -euo pipefail

log() {
    local level="$1"
    shift
    printf '[%s] [%s] %s\n' "$(date -u +"%Y-%m-%dT%H:%M:%SZ")" "$level" "$*"
}

maybe_run_prestart() {
    if [[ -n "${PRESTART_CMD:-}" ]]; then
        log INFO "Running PRESTART_CMD: ${PRESTART_CMD}"
        # shellcheck disable=SC2086
        bash -lc "${PRESTART_CMD}"
    fi

    if [[ -n "${PRESTART_SCRIPT:-}" ]]; then
        if [[ -x "${PRESTART_SCRIPT}" ]]; then
            log INFO "Executing PRESTART_SCRIPT: ${PRESTART_SCRIPT}"
            "${PRESTART_SCRIPT}"
        elif [[ -f "${PRESTART_SCRIPT}" ]]; then
            log INFO "Sourcing PRESTART_SCRIPT: ${PRESTART_SCRIPT}"
            # shellcheck disable=SC1090
            source "${PRESTART_SCRIPT}"
        else
            log WARN "PRESTART_SCRIPT path '${PRESTART_SCRIPT}' does not exist; skipping"
        fi
    fi
}

build_default_command() {
    local app_module="${API_APP_MODULE:-azt3knet.api.main:app}"
    local host="${API_HOST:-0.0.0.0}"
    local port="${API_PORT:-8000}"
    local reload_flag="${API_RELOAD_FLAG:-}"

    CMD=(uvicorn "$app_module" --host "$host" --port "$port")
    if [[ -n "$reload_flag" ]]; then
        # shellcheck disable=SC2086
        CMD+=($reload_flag)
    fi
}

maybe_run_prestart

if [[ $# -eq 0 ]]; then
    build_default_command
else
    CMD=("$@")
fi

log INFO "Starting command: ${CMD[*]}"
exec "${CMD[@]}"
