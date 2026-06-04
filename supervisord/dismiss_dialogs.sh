#!/usr/bin/env bash
# ---------------------------------------------------------------
# Dialog dismisser — automatically detects and closes blocking
# MT5 dialog windows to keep the headless terminal running.
# ---------------------------------------------------------------
set -euo pipefail

echo "Starting MT5 popup dialog dismisser..."

while true; do
    # Search for all windows belonging to terminal64.exe
    WINDOW_IDS=$(DISPLAY=:1 xdotool search --class "terminal64.exe" 2>/dev/null || true)
    
    for WID in $WINDOW_IDS; do
        WNAME=$(DISPLAY=:1 xdotool getwindowname "$WID" 2>/dev/null || continue)
        
        case "$WNAME" in
            "Welcome to LiveUpdate"|"Open an Account"|"Log In"|"Attention!"|"Warning"|"Authorize"|"Confirm")
                echo "Detected blocking dialog: '${WNAME}'. Closing window ${WID}..."
                DISPLAY=:1 xdotool windowkill "$WID" 2>/dev/null || DISPLAY=:1 xdotool key --window "$WID" Escape 2>/dev/null
                ;;
        esac
    done
    sleep 2
done
