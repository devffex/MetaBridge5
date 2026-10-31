#!/usr/bin/env bash
# ---------------------------------------------------------------
# MetaBridge5 Terminal Execution Wrapper
# Intercepts termination signals (SIGTERM/SIGINT) to ensure
# wineserver flushes registry hives and DPAPI credentials cleanly.
# ---------------------------------------------------------------
set -euo pipefail

cleanup() {
    echo "[terminal-wrapper] Intercepted termination signal. Requesting MT5 graceful exit..."
    wine taskkill /IM terminal64.exe >/dev/null 2>&1 || true

    local count=0
    while kill -0 "${TERMINAL_PID}" 2>/dev/null && [ $count -lt 10 ]; do
        sleep 1
        count=$((count + 1))
    done

    if kill -0 "${TERMINAL_PID}" 2>/dev/null; then
        echo "[terminal-wrapper] MT5 did not exit in 10s. Force killing process..."
        kill -KILL "${TERMINAL_PID}" 2>/dev/null || true
    fi

    local wine_procs
    wine_procs=$(pgrep -f "python.*grpc_server" 2>/dev/null || true)
    if [ -z "${wine_procs}" ]; then
        echo "[terminal-wrapper] No other Wine processes active. Flushing wineserver state..."
        wineserver -w || true
        echo "[terminal-wrapper] Wine server terminated cleanly. Volume state committed."
    else
        echo "[terminal-wrapper] Auxiliary Wine services active. Leaving wineserver running."
    fi

    exit 0
}

trap cleanup SIGTERM SIGINT

echo "[terminal-wrapper] Starting MetaTrader 5 terminal..."
wine M:\\MetaTrader5\\terminal64.exe /portable &
TERMINAL_PID=$!

wait "${TERMINAL_PID}"
