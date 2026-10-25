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
RESOLVED_API_KEY="${METABRIDGE5_API_KEY:-dev_metabridge5_secret_key_123}"
RESOLVED_VNC_PASSWORD="${VNC_PASSWORD:-metabridge5pass}"

# If secrets files are present in tmpfs /run/secrets, load them
if [ -f "$API_KEY_FILE" ] && [ -f "$VNC_PASSWORD_FILE" ]; then
    RESOLVED_API_KEY=$(cat "$API_KEY_FILE")
    RESOLVED_VNC_PASSWORD=$(cat "$VNC_PASSWORD_FILE")
    echo "[Entrypoint] Secrets loaded successfully from ${SECRETS_DIR}."
fi

export METABRIDGE5_API_KEY="${RESOLVED_API_KEY}"
export VNC_PASSWORD="${RESOLVED_VNC_PASSWORD}"

# Run the standard supervisord command
exec /usr/bin/supervisord -c /etc/supervisord.conf
