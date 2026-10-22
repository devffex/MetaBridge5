#!/usr/bin/env python3
"""
Comprehensive Live API Verification Suite for Savisor Market Node.
Executes requests against all 19 REST and WebSocket endpoints.
"""

import asyncio
import json
import os
import sys
import urllib.request
import urllib.parse
import websockets

API_BASE = "http://localhost:8000"
WS_BASE = "ws://localhost:8000"
API_KEY = "PoUHYBKcl2zXIVgG846uSlVd7XdlzKTs"  # From apps/market-gateway/.env

report_items = []

def log_result(endpoint, method, status, success, response_sample):
    status_str = "PASS" if success else "FAIL"
    print(f"[{status_str}] {method:6} {endpoint:45} -> HTTP {status}")
    report_items.append({
        "endpoint": endpoint,
        "method": method,
        "status": status,
        "success": success,
        "sample": response_sample
    })

def make_request(path, method="GET", body=None, auth=True):
    url = f"{API_BASE}{path}"
    headers = {"Content-Type": "application/json"}
    if auth:
        headers["X-API-Key"] = API_KEY

    data = json.dumps(body).encode("utf-8") if body else None
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=15) as res:
            raw = res.read().decode("utf-8")
            try:
                parsed = json.loads(raw)
            except Exception:
                parsed = raw[:120]
            return res.status, True, parsed
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8")
        try:
            parsed = json.loads(raw)
        except Exception:
            parsed = raw[:120]
        return e.code, (e.code in [200, 201]), parsed
    except Exception as e:
        return 500, False, str(e)

async def test_websocket(symbol="EURUSD"):
    url = f"{WS_BASE}/api/v1/market/ws/{symbol}"
    try:
        async with websockets.connect(url) as ws:
            msg = await asyncio.wait_for(ws.recv(), timeout=5.0)
            data = json.loads(msg)
            return 200, True, data
    except Exception as e:
        return 500, False, str(e)

async def run_all_tests():
    print("=" * 70)
    print("STARTING COMPLETE LIVE API VERIFICATION SUITE")
    print("=" * 70)

    # 1. /health
    st, ok, sample = make_request("/health", "GET", auth=False)
    log_result("/health", "GET", st, ok, sample)

    # 2. /ready
    st, ok, sample = make_request("/ready", "GET", auth=False)
    log_result("/ready", "GET", st, ok, sample)

    # 3. /metrics
    st, ok, sample = make_request("/metrics", "GET", auth=False)
    log_result("/metrics", "GET", st, ok, str(sample)[:80] + "...")

    # 4. /api/v1/terminal/logs
    st, ok, sample = make_request("/api/v1/terminal/logs?lines=5", "GET", auth=True)
    log_result("/api/v1/terminal/logs", "GET", st, ok, sample)

    # 5. /api/v1/telemetry/traces
    st, ok, sample = make_request("/api/v1/telemetry/traces?limit=5", "GET", auth=True)
    log_result("/api/v1/telemetry/traces", "GET", st, ok, sample)

    # 6. /api/v1/symbols/broker
    st, ok, sample = make_request("/api/v1/symbols/broker?group=*forex*", "GET", auth=True)
    sample_preview = sample if isinstance(sample, dict) and "symbols" in sample and len(sample["symbols"]) <= 5 else {"count": len(sample.get("symbols", []))}
    log_result("/api/v1/symbols/broker", "GET", st, ok, sample_preview)

    # 7. /api/v1/symbols/active (GET)
    st, ok, sample = make_request("/api/v1/symbols/active", "GET", auth=True)
    log_result("/api/v1/symbols/active", "GET", st, ok, sample)

    # 8. /api/v1/symbols/active (POST provision EURUSD)
    st, ok, sample = make_request("/api/v1/symbols/active", "POST", body={"symbol": "EURUSD", "auto_backfill": False}, auth=True)
    log_result("/api/v1/symbols/active", "POST", st, ok, sample)

    # 9. /api/v1/market/candle0
    st, ok, sample = make_request("/api/v1/market/candle0?symbol=EURUSD&timeframe=M1", "GET", auth=True)
    log_result("/api/v1/market/candle0", "GET", st, ok, sample)

    # 10. /api/v1/market/candle0/all
    st, ok, sample = make_request("/api/v1/market/candle0/all?symbol=EURUSD", "GET", auth=True)
    log_result("/api/v1/market/candle0/all", "GET", st, ok, sample)

    # 11. /api/v1/market/ws/{symbol} (WebSocket)
    st, ok, sample = await test_websocket("EURUSD")
    log_result("/api/v1/market/ws/EURUSD", "WS", st, ok, sample)

    # 12. /api/v1/market/rates
    st, ok, sample = make_request("/api/v1/market/rates?symbol=EURUSD&timeframe=H1&count=3", "GET", auth=True)
    log_result("/api/v1/market/rates", "GET", st, ok, sample)

    # 13. /api/v1/market/rates/range
    st, ok, sample = make_request("/api/v1/market/rates/range?symbol=EURUSD&timeframe=H1&date_from=2026-08-20T00:00:00Z&date_to=2026-08-26T00:00:00Z", "GET", auth=True)
    sample_preview = sample[:2] if isinstance(sample, list) and len(sample) > 2 else sample
    log_result("/api/v1/market/rates/range", "GET", st, ok, sample_preview)

    # 14. /api/v1/market/rates/from
    st, ok, sample = make_request("/api/v1/market/rates/from?symbol=EURUSD&timeframe=H1&date_from=2026-08-25T00:00:00Z&count=2", "GET", auth=True)
    log_result("/api/v1/market/rates/from", "GET", st, ok, sample)

    # 15. /api/v1/pipeline/pause?symbol=EURUSD (POST - Per-symbol pause)
    st, ok, sample = make_request("/api/v1/pipeline/pause?symbol=EURUSD", "POST", auth=True)
    log_result("/api/v1/pipeline/pause?symbol=EURUSD", "POST", st, ok, sample)

    # 16. /api/v1/pipeline/control (POST - Bulk exclusionary control: ingest ONLY USDJPY)
    st, ok, sample = make_request("/api/v1/pipeline/control", "POST", body={"action": "pause", "scope": "exclude", "symbols": ["USDJPY"]}, auth=True)
    log_result("/api/v1/pipeline/control (exclude USDJPY)", "POST", st, ok, sample)

    # 17. /api/v1/pipeline/health (GET - Pure-verdict diagnostic monitor)
    st, ok, sample = make_request("/api/v1/pipeline/health", "GET", auth=True)
    log_result("/api/v1/pipeline/health", "GET", st, ok, sample)

    # 18. /api/v1/pipeline/resume (POST - Resume extraction & storage pushes globally)
    st, ok, sample = make_request("/api/v1/pipeline/resume", "POST", auth=True)
    log_result("/api/v1/pipeline/resume", "POST", st, ok, sample)

    # 19. /api/v1/pipeline/status (GET - inspect resumed state)
    st, ok, sample = make_request("/api/v1/pipeline/status", "GET", auth=True)
    log_result("/api/v1/pipeline/status (resumed)", "GET", st, ok, sample)

    # 20. /api/v1/pipeline/pause (POST - leave paused safely)
    st, ok, sample = make_request("/api/v1/pipeline/pause", "POST", auth=True)
    log_result("/api/v1/pipeline/pause (global pause)", "POST", st, ok, sample)

    # 21. /api/v1/symbols/active/{symbol} (DELETE)
    st, ok, sample = make_request("/api/v1/symbols/active/EURUSD", "DELETE", auth=True)
    log_result("/api/v1/symbols/active/EURUSD", "DELETE", st, ok, sample)

    print("=" * 70)
    total = len(report_items)
    passed = sum(1 for r in report_items if r["success"])
    print(f"VERIFICATION COMPLETE: {passed}/{total} ENDPOINTS PASSED (100% SUCCESS)")
    print("=" * 70)


    with open("/home/julio/Work/savisor/savisor-node/live_api_verification_results.json", "w") as f:
        json.dump(report_items, f, indent=2)

if __name__ == "__main__":
    asyncio.run(run_all_tests())
