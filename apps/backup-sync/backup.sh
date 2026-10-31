#!/bin/sh
set -eu

SOURCE_DIR="${VOLUME_MOUNT:-/source/account}"
BACKUP_DIR="/tmp/backups"
TIMESTAMP=$(date -u +"%Y%m%d_%H%M%S")
ARCHIVE_NAME="mt5_account_backup_${TIMESTAMP}.tar.gz"
REMOTE_DEST="${RCLONE_REMOTE_DEST:-}"

mkdir -p "${BACKUP_DIR}"

if [ ! -d "${SOURCE_DIR}" ]; then
    echo "[backup] ERROR: Source directory ${SOURCE_DIR} does not exist!" >&2
    exit 1
fi

if [ -f "${SOURCE_DIR}/system.reg" ]; then
    echo "[backup] Validated MT5 Wine registry in ${SOURCE_DIR}"
else
    echo "[backup] WARNING: system.reg not found in ${SOURCE_DIR}, backing up available files"
fi

echo "[backup] Creating atomic snapshot of ${SOURCE_DIR}..."
tar --exclude='*.log' --exclude='*.tmp' \
    -czf "${BACKUP_DIR}/${ARCHIVE_NAME}" -C "${SOURCE_DIR}" .

echo "[backup] Generating SHA-256 integrity hash..."
cd "${BACKUP_DIR}"
sha256sum "${ARCHIVE_NAME}" > "${ARCHIVE_NAME}.sha256"

if [ -n "${REMOTE_DEST}" ]; then
    echo "[backup] Uploading archive to remote: ${REMOTE_DEST}/${ARCHIVE_NAME}..."
    rclone copyto "${BACKUP_DIR}/${ARCHIVE_NAME}" "${REMOTE_DEST}/${ARCHIVE_NAME}"
    rclone copyto "${BACKUP_DIR}/${ARCHIVE_NAME}.sha256" "${REMOTE_DEST}/${ARCHIVE_NAME}.sha256"
    echo "[backup] Upload complete. Purging local temporary archive..."
    rm -f "${BACKUP_DIR}/${ARCHIVE_NAME}" "${BACKUP_DIR}/${ARCHIVE_NAME}.sha256"
else
    echo "[backup] No RCLONE_REMOTE_DEST configured; keeping local archive in ${BACKUP_DIR}/${ARCHIVE_NAME}"
fi

touch /tmp/backup.heartbeat
echo "[backup] Backup finished successfully at $(date -u)"
