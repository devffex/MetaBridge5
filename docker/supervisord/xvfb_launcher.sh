#!/usr/bin/env bash
# ---------------------------------------------------------------
# MetaBridge5 Virtual Framebuffer Launcher
# Starts low-resource 800x600x16 buffer in headless mode,
# or standard 1280x800x16 buffer when START_VNC=true.
# ---------------------------------------------------------------
set -euo pipefail

if [ "${START_VNC:-false}" = "true" ]; then
    echo "[xvfb-launcher] Provisioning mode active. Starting standard display buffer (1280x800x16)..."
    exec Xvfb :1 -screen 0 1280x800x16 -nolisten tcp -noreset
else
    echo "[xvfb-launcher] Headless production mode active. Starting minimal display buffer (800x600x16)..."
    exec Xvfb :1 -screen 0 800x600x16 -nolisten tcp -noreset
fi
