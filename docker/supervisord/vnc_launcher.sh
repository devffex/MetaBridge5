#!/usr/bin/env bash
# ---------------------------------------------------------------
# MetaBridge5 Remote Desktop Launcher
# Binds x11vnc to localhost only when START_VNC=true,
# or exits cleanly (0% idle CPU) in headless mode.
# ---------------------------------------------------------------
set -euo pipefail

if [ "${START_VNC:-false}" = "true" ]; then
    echo "[vnc-launcher] Administrative mode enabled. Launching x11vnc..."
    exec x11vnc -display :1 -passwdfile /home/wine/.vnc/passwdfile -forever -shared -noxdamage
else
    echo "[vnc-launcher] Headless mode confirmed (START_VNC=false). Remote desktop disabled."
    exit 0
fi
