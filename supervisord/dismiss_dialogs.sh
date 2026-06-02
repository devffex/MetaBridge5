#!/bin/bash
echo "Starting MT5 popup dialog dismisser..."

while true; do
    # Search for all windows belonging to terminal64.exe
    WINDOW_IDS=$(DISPLAY=:1 xdotool search --class "terminal64.exe" 2>/dev/null)
    for WID in $WINDOW_IDS; do
        WNAME=$(DISPLAY=:1 xdotool getwindowname $WID 2>/dev/null)
        
        # 1. Close LiveUpdate window
        if [ "$WNAME" = "Welcome to LiveUpdate" ]; then
            echo "Detected LiveUpdate dialog. Closing..."
            DISPLAY=:1 xdotool windowkill $WID 2>/dev/null || DISPLAY=:1 xdotool key --window $WID Escape 2>/dev/null
        fi
    done
    sleep 2
done
