#!/usr/bin/env bash
# -----------------------------------------------------------------------------
# MetaBridge5 Core Container Healthcheck
# Verifies gRPC server port 50051 is listening and terminal64.exe is alive.
# -----------------------------------------------------------------------------
set -eo pipefail

# 1. Check gRPC port responsiveness
if ! timeout 2 bash -c "</dev/tcp/127.0.0.1/50051" >/dev/null 2>&1; then
    exit 1
fi

# 2. Check terminal process
if ! pgrep -f "terminal64.exe" >/dev/null 2>&1; then
    exit 1
fi

exit 0
