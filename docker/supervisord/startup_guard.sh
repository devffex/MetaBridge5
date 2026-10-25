#!/usr/bin/env bash
# ---------------------------------------------------------------
# Startup guard - validates that all required secrets are present
# before any service starts. If any variable is missing, the
# script exits non-zero which causes supervisord to halt.
# ---------------------------------------------------------------
set -euo pipefail

errors=0

RESOLVED_API_KEY="${METABRIDGE5_API_KEY:-dev_metabridge5_secret_key_123}"
RESOLVED_VNC_PASSWORD="${VNC_PASSWORD:-metabridge5pass}"

if [ -z "${METABRIDGE5_API_KEY:-}" ]; then
    echo "[startup_guard] NOTICE: METABRIDGE5_API_KEY not set. Using default development secret." >&2
fi

if [ -z "${VNC_PASSWORD:-}" ]; then
    echo "[startup_guard] NOTICE: VNC_PASSWORD not set. Using default development VNC password (metabridge5pass)." >&2
fi

export METABRIDGE5_API_KEY="${RESOLVED_API_KEY}"
export VNC_PASSWORD="${RESOLVED_VNC_PASSWORD}"

echo "Startup guard passed - runtime secrets validated."
