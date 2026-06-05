#!/usr/bin/env bash
# ---------------------------------------------------------------
# Writes the VNC password file from the VNC_PASSWORD env var.
# Must run before x11vnc starts (managed via supervisord priority).
# ---------------------------------------------------------------
set -euo pipefail

PASSWD_DIR="/home/wine/.vnc"
PASSWD_FILE="${PASSWD_DIR}/passwd"

if [ -z "${VNC_PASSWORD:-}" ]; then
    echo "FATAL: VNC_PASSWORD environment variable is not set." >&2
    exit 1
fi

mkdir -p "$PASSWD_DIR"

# x11vnc -storepasswd writes the password in VNC's native format
x11vnc -storepasswd "$VNC_PASSWORD" "$PASSWD_FILE"

chmod 600 "$PASSWD_FILE"

echo "VNC password file written to ${PASSWD_FILE}."
