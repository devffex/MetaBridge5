#!/usr/bin/env bash
# ---------------------------------------------------------------
# Writes the VNC password file from the VNC_PASSWORD env var.
# Must run before x11vnc starts (managed via supervisord priority).
# ---------------------------------------------------------------
set -euo pipefail

PASSWD_DIR="/home/wine/.vnc"
PASSWD_FILE="${PASSWD_DIR}/passwd"
PASSWDFILE_LIST="${PASSWD_DIR}/passwdfile"

VNC_PASSWORD="${VNC_PASSWORD:-metabridge5pass}"

mkdir -p "$PASSWD_DIR"

# Generate multi-password list for x11vnc -passwdfile to allow flexible casing
# (e.g. metabridge5pass, Metabridge5Pass, MetaBridge5Pass)
rm -f "$PASSWDFILE_LIST"
touch "$PASSWDFILE_LIST"

echo "$VNC_PASSWORD" >> "$PASSWDFILE_LIST"

# Add lowercase variation
echo "${VNC_PASSWORD,,}" >> "$PASSWDFILE_LIST"

# If the password is a variation of metabridge5pass, ensure all standard casing variants are accepted
if [ "${VNC_PASSWORD,,}" = "metabridge5pass" ]; then
    echo "metabridge5pass" >> "$PASSWDFILE_LIST"
    echo "Metabridge5Pass" >> "$PASSWDFILE_LIST"
    echo "MetaBridge5Pass" >> "$PASSWDFILE_LIST"
fi

# Remove duplicates while preserving line order
awk '!seen[$0]++' "$PASSWDFILE_LIST" > "${PASSWDFILE_LIST}.tmp" && mv "${PASSWDFILE_LIST}.tmp" "$PASSWDFILE_LIST"
chmod 600 "$PASSWDFILE_LIST"

# Also write standard x11vnc rfbauth file
x11vnc -storepasswd "$VNC_PASSWORD" "$PASSWD_FILE"
chmod 600 "$PASSWD_FILE"

echo "VNC password configured successfully in ${PASSWDFILE_LIST} and ${PASSWD_FILE}."
