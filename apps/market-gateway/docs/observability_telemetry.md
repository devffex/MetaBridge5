# Observability, Logs & Telemetry Guide

This guide covers the 4 diagnostic and observability layers provided by the Savisor Market Node.

---

## 1. MetaTrader 5 Platform Journal Logs (`GET /api/v1/terminal/logs`)

MetaTrader 5 automatically writes its daily platform journal logs inside the container to `/home/wine/.wine/drive_c/MetaTrader5/logs/YYYYMMDD.log` in UTF-16-LE encoding.

The node provides a dedicated REST endpoint to stream, decode, and tail these logs directly without opening a terminal session:

```bash
# Tail the latest 50 lines from today's MT5 log file
curl -s -H "X-API-Key: your_secret_api_key_here" \
  "http://localhost:8000/api/v1/terminal/logs?lines=50"
```

**Sample Response**:
```json
{
  "file": "20260826.log",
  "total_lines": 124,
  "returned_lines": 3,
  "lines": [
    "Terminal: MetaTrader 5 x64 build 5836 started for MetaQuotes Ltd.",
    "Network: '111718618': authorized on MetaQuotes-Demo through Access Point 29",
    "Network: '111718618': previous successful authorization performed on 2026.08.26"
  ]
}
```

---

## 2. Internal SQLite WAL Audit Traces (`GET /api/v1/telemetry/traces`)

The node records lifecycle events, pipeline jobs, and operational metrics into an embedded SQLite database running in **WAL (Write-Ahead Logging)** mode (`/tmp/savisor_traces.sqlite3`), achieving microsecond write latency without blocking API traffic.

```bash
# Query recent audit traces for EURUSD
curl -s -H "X-API-Key: your_secret_api_key_here" \
  "http://localhost:8000/api/v1/telemetry/traces?symbol=EURUSD&limit=10"
```

**Sample Response**:
```json
{
  "sink": "SQLiteAuditSink",
  "count": 2,
  "traces": [
    {
      "id": "bb741dd8-fd57-4ca7-960f-d33a0568dc62",
      "timestamp": 1787768485,
      "trace_id": "f7c21973",
      "component": "pipeline",
      "event": "backfill_started",
      "symbol": "EURUSD",
      "status": "info",
      "metadata": {
        "timeframes": ["M1", "M5", "M15", "M30", "H1", "H4", "D1"],
        "candle_count": 5000
      }
    }
  ]
}
```

---

## 3. Prometheus Metrics Scrape (`GET /metrics`)

The node exports standard Prometheus metrics for alerting, latency tracking, and Grafana dashboard visualization:

```bash
curl -s http://localhost:8000/metrics | head -n 30
```

### Key Metrics Exported

| Metric Name | Type | Description |
|---|---|---|
| `savisor_ticks_processed_total{symbol="EURUSD"}` | Counter | Total market price ticks processed. |
| `savisor_candle0_updates_total{symbol="EURUSD", timeframe="M1"}` | Counter | In-flight Candle 0 updates performed. |
| `savisor_candle0_closes_total{symbol="EURUSD", timeframe="M1"}` | Counter | Number of finalized candle rollover events. |
| `savisor_active_ws_connections{symbol="EURUSD"}` | Gauge | Number of active connected WebSocket clients. |
| `savisor_backfill_duration_seconds_bucket` | Histogram | Backfill pipeline latency distribution. |

---

## 4. Live Container Process Tree (`docker top`)

Verify that all internal Linux and Windows/Wine processes are active in RAM without needing an SSH shell:

```bash
docker top savisor-market-node
```

**Expected Processes**:
1. `/usr/bin/supervisord` (Root process manager)
2. `python3 -m uvicorn app.main:app` (FastAPI / WebSocket gateway)
3. `C:\python\python.exe C:\daemon\grpc_server.py 50051` (MT5 gRPC daemon)
4. `Xvfb :1 -screen 0 1920x1080x16` (Virtual display buffer)
5. `C:\MetaTrader5\terminal64.exe /portable` (Native MT5 terminal)
6. `x11vnc -display :1` (TigerVNC remote desktop server)
