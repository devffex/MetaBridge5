#!/usr/bin/env bash
# ---------------------------------------------------------------
# MetaBridge5 Container Entrypoint Script
# ---------------------------------------------------------------
set -euo pipefail

# Path where manager mounts tmpfs and writes secrets dynamically
SECRETS_DIR="/run/secrets"
API_KEY_FILE="${SECRETS_DIR}/api_key"
VNC_PASSWORD_FILE="${SECRETS_DIR}/vnc_password"

# Resolve existing environment variables
RESOLVED_API_KEY="${METABRIDGE5_API_KEY:-}"

# If environment variables are already set, we skip waiting (for manual run compat)
if [ -n "${RESOLVED_API_KEY}" ] && [ -n "${VNC_PASSWORD:-}" ]; then
    echo "[Entrypoint] Secrets already present in environment variables. Proceeding."
    export METABRIDGE5_API_KEY="${RESOLVED_API_KEY}"
else
    echo "[Entrypoint] Waiting for secrets injection in ${SECRETS_DIR}..."
    # Poll up to 15 seconds for secrets files to be written by the manager
    for i in {1..15}; do
        if [ -f "$API_KEY_FILE" ] && [ -f "$VNC_PASSWORD_FILE" ]; then
            RESOLVED_API_KEY=$(cat "$API_KEY_FILE")
            export METABRIDGE5_API_KEY="${RESOLVED_API_KEY}"
            export VNC_PASSWORD=$(cat "$VNC_PASSWORD_FILE")
            echo "[Entrypoint] Secrets loaded successfully from ${SECRETS_DIR}."
            break
        fi
        sleep 1
    done
fi

# Assert that secrets are loaded
if [ -z "${METABRIDGE5_API_KEY:-}" ] || [ -z "${VNC_PASSWORD:-}" ]; then
    echo "FATAL: METABRIDGE5_API_KEY or VNC_PASSWORD could not be retrieved. Aborting." >&2
    exit 1
fi

# Run the standard supervisord command
exec /usr/bin/supervisord -c /etc/supervisord.conf
