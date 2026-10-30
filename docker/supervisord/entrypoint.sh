#!/usr/bin/env bash
# ---------------------------------------------------------------
# MetaBridge5 Container Entrypoint Script
# ---------------------------------------------------------------
set -euo pipefail

TARGET_UID="${PUID:-1000}"
TARGET_GID="${PGID:-1000}"

# Purge orphaned X11 lock files from unexpected terminations
rm -f /tmp/.X1-lock /tmp/.X11-unix/X1

WINE_PREFIX="${WINEPREFIX:-/home/wine/.wine}"
SEED_DIR="/opt/wine-seed"
APP_DIR="/opt/metabridge5"

# Populate fresh volumes from the pre-baked template
if [ ! -f "${WINE_PREFIX}/system.reg" ]; then
    echo "[entrypoint] Uninitialized volume detected. Seeding prefix from ${SEED_DIR}..."
    cp -a "${SEED_DIR}/." "${WINE_PREFIX}/"
    echo "[entrypoint] Seed deployment completed in sub-second time."
elif [ ! -d "${WINE_PREFIX}/drive_c/mt5-data" ]; then
    echo "[entrypoint] Existing volume missing mt5-data. Migrating mt5-data template..."
    mkdir -p "${WINE_PREFIX}/drive_c"
    cp -a "${SEED_DIR}/drive_c/mt5-data" "${WINE_PREFIX}/drive_c/"
fi

mkdir -p "${WINE_PREFIX}/dosdevices"
ln -sfn "${APP_DIR}" "${WINE_PREFIX}/dosdevices/m:"
rm -f "${WINE_PREFIX}/dosdevices/z:"

# Reconcile volume ownership when running with root privileges
if [ "$(id -u)" = "0" ]; then
    CURRENT_WINE_UID=$(id -u wine 2>/dev/null || echo "")
    CURRENT_WINE_GID=$(id -g wine 2>/dev/null || echo "")
    if [ -n "${CURRENT_WINE_UID}" ] && [ "${TARGET_UID}" != "${CURRENT_WINE_UID}" ]; then
        sed -i -e "s/^wine:x:${CURRENT_WINE_UID}:/wine:x:${TARGET_UID}:/" /etc/passwd
    fi
    if [ -n "${CURRENT_WINE_GID}" ] && [ "${TARGET_GID}" != "${CURRENT_WINE_GID}" ]; then
        sed -i -e "s/^wine:x:[0-9]*:${CURRENT_WINE_GID}:/wine:x:${TARGET_UID}:${TARGET_GID}:/" /etc/passwd 2>/dev/null || true
        sed -i -e "s/^wine:x:${CURRENT_WINE_GID}:/wine:x:${TARGET_GID}:/" /etc/group 2>/dev/null || true
    fi

    mkdir -p /home/wine/.vnc
    CURRENT_OWNER=$(stat -c "%u:%g" "${WINE_PREFIX}" 2>/dev/null || echo "")
    if [ "${CURRENT_OWNER}" != "${TARGET_UID}:${TARGET_GID}" ]; then
        echo "[entrypoint] Volume ownership mismatch (${CURRENT_OWNER} != ${TARGET_UID}:${TARGET_GID}). Aligning permissions..."
        chown -R "${TARGET_UID}:${TARGET_GID}" /home/wine/.wine /home/wine/.vnc
        if [ -d /home/wine/app ]; then
            chown -R "${TARGET_UID}:${TARGET_GID}" /home/wine/app
        fi
    fi
fi

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

CMD=( "$@" )
if [ $# -eq 0 ]; then
    CMD=( /usr/bin/supervisord -c /etc/supervisord.conf )
fi

# Drop privileges if running as root
if [ "$(id -u)" = "0" ]; then
    exec su-exec "${TARGET_UID}:${TARGET_GID}" "${CMD[@]}"
else
    exec "${CMD[@]}"
fi
