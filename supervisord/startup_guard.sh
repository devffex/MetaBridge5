#!/usr/bin/env bash
# ---------------------------------------------------------------
# Startup guard — validates that all required secrets are present
# before any service starts.  If any variable is missing, the
# script exits non-zero which causes supervisord to halt.
# ---------------------------------------------------------------
set -euo pipefail

errors=0

if [ -z "${SAVISOR_API_KEY:-}" ]; then
    echo "FATAL: SAVISOR_API_KEY environment variable is not set." >&2
    errors=$((errors + 1))
fi

if [ -z "${VNC_PASSWORD:-}" ]; then
    echo "FATAL: VNC_PASSWORD environment variable is not set." >&2
    errors=$((errors + 1))
fi

if [ "$errors" -gt 0 ]; then
    echo "Aborting: $errors required secret(s) missing. Set them via 'docker run -e'." >&2
    exit 1
fi

echo "Startup guard passed — all required secrets are present."
