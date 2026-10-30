#!/usr/bin/env bash
# ---------------------------------------------------------------
# MetaBridge5 Container Entrypoint Script
# ---------------------------------------------------------------
set -euo pipefail

WINE_PREFIX="${WINEPREFIX:-/home/wine/.wine}"
SEED_DIR="/opt/wine-seed"
APP_DIR="/opt/metabridge5"

# Populate fresh volumes from the pre-baked template
if [ ! -f "${WINE_PREFIX}/system.reg" ]; then
    echo "[entrypoint] Uninitialized volume detected. Seeding prefix from ${SEED_DIR}..."
    cp -a "${SEED_DIR}/." "${WINE_PREFIX}/"
    echo "[entrypoint] Seed deployment completed in sub-second time."
fi

mkdir -p "${WINE_PREFIX}/dosdevices"
ln -sfn "${APP_DIR}" "${WINE_PREFIX}/dosdevices/m:"
rm -f "${WINE_PREFIX}/dosdevices/z:"

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

if [ $# -eq 0 ]; then
    exec /usr/bin/supervisord -c /etc/supervisord.conf
else
    exec "$@"
fi
