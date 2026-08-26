# Savisor Market Data & Pipeline Node

The **Savisor Market Data & Pipeline Node** is a self-contained, high-performance financial data collection, real-time streaming, and historical ingestion engine. It runs MetaTrader 5 inside an optimized Wine runtime alongside a FastAPI/WebSocket server and an automated data pipeline worker managed by supervisord.

---

## 1. Architectural Highlights

* **Pluggable Storage Factory (`StorageBackend`)**:
  * **GitHub Public Repository (`github`)**: 100% free CDN hosting via Git REST API commits, accessible globally via `raw.githubusercontent.com` or Cloudflare proxy.
  * **S3 / Cloudflare R2 (`s3`)**: High-performance object storage with $0 egress fees (Cloudflare R2) and automatic cache-control headers.
  * **Local Filesystem (`local`)**: Development staging and offline testing.
* **Apache Parquet & Compact JSON Exporter**:
  * Historical candle partitions stored in compressed Apache Parquet (`<symbol>/<timeframe>/history.parquet`) and compact JSON (`<symbol>/<timeframe>/recent.json`).
* **Real-Time Candle 0 State Engine**:
  * Accumulates live market ticks in memory into the active forming candle (Candle 0).
  * Automatically rolls closed candles into historical datasets when period boundaries pass, eliminating data gaps.
* **Decoupled WebSocket Broadcaster**:
  * Handles up to 1,000 concurrent client connections over WebSockets with minimal CPU footprint and zero terminal overloading.
* **Observability & Telemetry**:
  * Dual audit logging factory (Internal SQLite in WAL mode + Remote External DB Sink), Prometheus metrics (`/metrics`), structured logging, and health/readiness probes (`/health`, `/ready`).

---

## 2. Quick Start

### A. Run with Docker Compose
```bash
# Launch container with local storage
docker compose up -d

# Verify health
curl -i http://localhost:8000/health
```

### B. Run with GitHub Storage Backend (Free CDN)
```bash
docker run -d --name savisor-market-node \
  -p 8000:8000 \
  -p 5900:5900 \
  -e SAVISOR_API_KEY="your-secret-api-key" \
  -e STORAGE_BACKEND="github" \
  -e GITHUB_TOKEN="ghp_xxx" \
  -e GITHUB_REPO="your-org/market-data" \
  -e GITHUB_BRANCH="main" \
  -e AUDIT_LOG_SINK="sqlite" \
  savisor-market-node:latest
```

---

## 3. API Directory

### Telemetry & Health
* `GET /health` — Node and daemon liveness probe (Public).
* `GET /ready` — Node readiness probe (Public).
* `GET /metrics` — Prometheus metrics scrape endpoint (Public).
* `GET /api/v1/telemetry/traces` — Query internal SQLite WAL audit logs.

### Real-Time Market Feed & Candle 0
* `GET /api/v1/market/candle0?symbol=EURUSD&timeframe=M1` — Instant in-flight Candle 0 state.
* `GET /api/v1/market/candle0/all?symbol=EURUSD` — Active Candle 0 states across all timeframes.
* `WS /api/v1/market/ws/{symbol}` — Real-time WebSocket streaming live ticks and Candle 0 states.

*(Legacy `/api/v1/chart/...` routes are supported as backward-compatible aliases)*

### Data Pipeline & Backfill
* `POST /api/v1/pipeline/backfill` — Trigger on-demand deep historical backfill across timeframes.
  * Body: `{"symbol": "EURUSD", "timeframes": ["M1", "M5", "H1", "D1"], "candle_count": 10000}`
* `GET /api/v1/pipeline/status` — Inspect backfill worker status registry.

### Historical Rates
* `GET /api/v1/market/rates?symbol=EURUSD&timeframe=H1&count=500` — Retrieve compact candle array from terminal cache.
* `GET /api/v1/market/rates/range` — Retrieve candles by ISO date range.
* `GET /api/v1/market/rates/from` — Retrieve candles from starting timestamp.

### Dynamic Symbol Provisioning
* `GET /api/v1/symbols/active` — List actively tracked assets.
* `POST /api/v1/symbols/active` — Add/provision symbol and trigger automatic backfill.
  * Body: `{"symbol": "EURUSD", "auto_backfill": true, "candle_count": 10000}`
* `DELETE /api/v1/symbols/active/{symbol}` — De-provision symbol.

---

## 4. Testing & Verification

Run the full automated test suite:
```bash
PYTHONPATH=apps/market-gateway uv run --project apps/market-gateway pytest apps/market-gateway/tests -v
```

---

## 5. Complete Client Integration Documentation

For complete client integration examples (TradingView Lightweight Charts in React/TypeScript, Python Trading Bots with indicator warmup, DuckDB / Polars ML pipelines, and full REST/WS schema specs), see:
👉 **[Client API & Integration Guide](../../docs/client_api.md)**
