#!/usr/bin/env bash
# -----------------------------------------------------------------------------
# MetaBridge5 Container Image Size Verification Gate
# Enforces strict hard upper bounds on built image sizes to prevent bloat.
# -----------------------------------------------------------------------------
set -euo pipefail

# Budget thresholds in Megabytes (1 MB = 1,000,000 bytes)
CORE_MAX_MB=530
GATEWAY_MAX_MB=125
ANALYTICS_MAX_MB=150
BACKUP_MAX_MB=60
COMBINED_MAX_MB=650

declare -A BUDGETS=(
    ["metabridge5-core:latest"]=${CORE_MAX_MB}
    ["metabridge5-market-gateway:latest"]=${GATEWAY_MAX_MB}
    ["metabridge5-duckdb-analytics:latest"]=${ANALYTICS_MAX_MB}
    ["metabridge5-backup-sync:latest"]=${BACKUP_MAX_MB}
)

echo "============================================================"
echo " MetaBridge5 Container Image Size Audit"
echo "============================================================"

FAILED=0

for IMAGE in "${!BUDGETS[@]}"; do
    BUDGET_MB=${BUDGETS[$IMAGE]}
    
    if ! docker image inspect "${IMAGE}" >/dev/null 2>&1; then
        echo "[-] ${IMAGE}: NOT FOUND (skip)"
        continue
    fi
    
    BYTES=$(docker image inspect "${IMAGE}" --format '{{.Size}}')
    MB=$(awk -v b="$BYTES" 'BEGIN { printf "%.1f", b / 1000000 }')
    INT_MB=$(awk -v b="$BYTES" 'BEGIN { printf "%d", b / 1000000 }')
    
    if [ "$INT_MB" -gt "$BUDGET_MB" ]; then
        echo "[!] FAIL: ${IMAGE} is ${MB} MB (Budget: ${BUDGET_MB} MB, exceeded by $((INT_MB - BUDGET_MB)) MB)"
        FAILED=1
    else
        MARGIN=$((BUDGET_MB - INT_MB))
        echo "[+] PASS: ${IMAGE} is ${MB} MB (Budget: ${BUDGET_MB} MB, margin: ${MARGIN} MB)"
    fi
done

# Check combined core + gateway footprint
if docker image inspect "metabridge5-core:latest" >/dev/null 2>&1 && \
   docker image inspect "metabridge5-market-gateway:latest" >/dev/null 2>&1; then
    CORE_BYTES=$(docker image inspect "metabridge5-core:latest" --format '{{.Size}}')
    GW_BYTES=$(docker image inspect "metabridge5-market-gateway:latest" --format '{{.Size}}')
    TOTAL_BYTES=$((CORE_BYTES + GW_BYTES))
    TOTAL_MB=$(awk -v b="$TOTAL_BYTES" 'BEGIN { printf "%.1f", b / 1000000 }')
    INT_TOTAL_MB=$(awk -v b="$TOTAL_BYTES" 'BEGIN { printf "%d", b / 1000000 }')
    
    if [ "$INT_TOTAL_MB" -gt "$COMBINED_MAX_MB" ]; then
        echo "[!] FAIL: Combined core + gateway is ${TOTAL_MB} MB (Budget: ${COMBINED_MAX_MB} MB)"
        FAILED=1
    else
        echo "[+] PASS: Combined core + gateway is ${TOTAL_MB} MB (Budget: ${COMBINED_MAX_MB} MB)"
    fi
fi

echo "============================================================"
if [ $FAILED -ne 0 ]; then
    echo "ERROR: One or more container images broke the size budget!"
    exit 1
fi
echo "SUCCESS: All container images passed size budget verification."
exit 0
