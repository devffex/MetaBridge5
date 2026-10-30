#!/usr/bin/env bash
# ---------------------------------------------------------------
# MetaBridge5 Terminal Execution Wrapper
# Intercepts termination signals (SIGTERM/SIGINT) to ensure
# wineserver flushes registry hives and DPAPI credentials cleanly.
# ---------------------------------------------------------------
set -euo pipefail

cleanup() {
    echo "[terminal-wrapper] Intercepted termination signal. Flushing Wine server..."
    wineserver -k || true
    wineserver -w || true
    echo "[terminal-wrapper] Wine server terminated cleanly. Volume state committed."
    exit 0
}

trap cleanup SIGTERM SIGINT

echo "[terminal-wrapper] Starting MetaTrader 5 terminal..."
wine M:\\MetaTrader5\\terminal64.exe /portable &
TERMINAL_PID=$!

wait "${TERMINAL_PID}"
