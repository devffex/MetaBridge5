#!/bin/sh
set -eu

TARGET_DIR="${TARGET_DIR:-/source/account}"
RESTORE_ARCHIVE="${RESTORE_ARCHIVE:-}"
REMOTE_SRC="${RCLONE_REMOTE_SRC:-}"
STAGING_DIR="/tmp/restore"

mkdir -p "${TARGET_DIR}" "${STAGING_DIR}"

if [ -z "${RESTORE_ARCHIVE}" ] && [ -n "${REMOTE_SRC}" ]; then
    echo "[restore] Discovering latest archive from remote ${REMOTE_SRC}..."
    LATEST=$(rclone lsf "${REMOTE_SRC}" --include "*.tar.gz" | sort -r | head -n 1)
    if [ -z "${LATEST}" ]; then
        echo "[restore] ERROR: No .tar.gz archives found in ${REMOTE_SRC}!" >&2
        exit 1
    fi
    echo "[restore] Downloading ${LATEST} and signature..."
    rclone copyto "${REMOTE_SRC}/${LATEST}" "${STAGING_DIR}/${LATEST}"
    rclone copyto "${REMOTE_SRC}/${LATEST}.sha256" "${STAGING_DIR}/${LATEST}.sha256"
    RESTORE_ARCHIVE="${STAGING_DIR}/${LATEST}"
fi

if [ -z "${RESTORE_ARCHIVE}" ] || [ ! -f "${RESTORE_ARCHIVE}" ]; then
    echo "[restore] ERROR: No valid archive file specified or found!" >&2
    exit 1
fi

SHA_FILE="${RESTORE_ARCHIVE}.sha256"
if [ -f "${SHA_FILE}" ]; then
    echo "[restore] Verifying SHA-256 integrity signature..."
    ARCHIVE_DIR=$(dirname "${RESTORE_ARCHIVE}")
    ARCHIVE_FILE=$(basename "${RESTORE_ARCHIVE}")
    (cd "${ARCHIVE_DIR}" && sha256sum -c "${ARCHIVE_FILE}.sha256")
    echo "[restore] Signature verification passed."
else
    echo "[restore] WARNING: No checksum file found; skipping checksum verification."
fi

echo "[restore] Extracting archive into ${TARGET_DIR}..."
tar -xzf "${RESTORE_ARCHIVE}" -C "${TARGET_DIR}"

# Ensure correct UID/GID ownership if running as root
if [ "$(id -u)" = "0" ]; then
    echo "[restore] Setting ownership to UID 1000:1000..."
    chown -R 1000:1000 "${TARGET_DIR}"
fi

rm -rf "${STAGING_DIR}"
echo "[restore] Restoration completed successfully into ${TARGET_DIR} at $(date -u)"
