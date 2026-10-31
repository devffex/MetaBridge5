#!/bin/sh
set -eu

PARQUET_SRC="${PARQUET_SRC:-/source/data/parquet}"
PARQUET_DEST="${PARQUET_DEST:-}"
BWLIMIT="${BWLIMIT:-2M}"

if [ -z "${PARQUET_DEST}" ]; then
    echo "[sync-parquet] PARQUET_DEST not set; skipping synchronization."
    exit 0
fi

if [ ! -d "${PARQUET_SRC}" ]; then
    echo "[sync-parquet] Source directory ${PARQUET_SRC} does not exist; skipping."
    exit 0
fi

echo "[sync-parquet] Synchronizing Parquet datasets from ${PARQUET_SRC} to ${PARQUET_DEST} (bwlimit: ${BWLIMIT})..."
rclone sync "${PARQUET_SRC}" "${PARQUET_DEST}" --bwlimit "${BWLIMIT}" --transfers 4 --checkers 8
echo "[sync-parquet] Parquet synchronization complete at $(date -u)"
