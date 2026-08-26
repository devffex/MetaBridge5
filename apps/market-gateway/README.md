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

## Operational Workflow: Manual vs. Automated Operations

> [!IMPORTANT]
> **Zero Manual Chart Clicking Required**:
> You do **NOT** need to open MetaTrader 5 chart windows, scroll through historical bars, or manually click on `M1`, `M5`, `H1`, `D1` timeframe buttons to download broker history.
>
> The MetaTrader 5 terminal daemon automatically communicates with the broker's trade servers and downloads requested history in the background. Once logged into your broker account, **all further operations are 100% automated via REST and WebSocket APIs**.

### Operational Breakdown

| Operation | Mode | How It Works |
|---|---|---|
| **Broker Account Login** | **One-Time Setup** | Connect once via TigerVNC (`vncviewer localhost:5900`, password: `savisorpass`) to log in to your broker account, or pre-authenticate in the portable `MetaTrader5/` directory before building. |
| **Asset Watchlist Activation** | **100% Automated** | Call `POST /api/v1/symbols/active` with `{"symbol": "EURUSD"}`. The node activates the symbol in the broker's Market Watch. |
| **Broker History Downloads** | **100% Automated** | `BackfillWorker` queries MT5 via gRPC. The terminal daemon automatically downloads missing history from the broker in the background. |
| **Multi-Timeframe Generation (`M1`..`MN1`)** | **100% Automated** | Automatically generates datasets across all timeframes without opening chart windows. |
| **Parquet & Compact JSON Exports** | **100% Automated** | Compresses historical bars into Apache Parquet (`history.parquet`) and compact JSON (`recent.json`). |
| **Multi-CDN Sync & Edge Cache Purge** | **100% Automated** | Commits datasets to GitHub (`devffex/dataset`) and purges the jsDelivr edge cache automatically. |
| **Live Tick & Candle 0 Streaming** | **100% Automated** | Streams live ticks and aggregates the active forming Candle 0 over WebSockets (`WS /api/v1/market/ws/{symbol}`). |

---

## 2. Quick Start & Local Build

> [!IMPORTANT]
> **Build Locally First (Avoid "pull access denied")**:
> The `savisor-market-node:latest` image is built locally within this monorepo and is **not published on public Docker Hub**.
> If you execute `docker run savisor-market-node:latest` before building, Docker will attempt to pull the image from Docker Hub and fail with `pull access denied`.
>
> Build and run the image from the **monorepo root directory**:

### Option A: Using Docker Compose (Simplest)
From the monorepo root:
```bash
# Automatically builds and starts the container in one command:
docker compose up -d --build

# Follow live container logs:
docker compose logs -f
```

### Option B: Using Makefile & Docker Run (Two-Step Local Build)
From the monorepo root:
```bash
# 1. Build the shared Wine + MT5 base image
make build-base

# 2. Build the market node image
make build-market-node

# 3. Run the container
docker run -d --name savisor-market-node \
  -p 8000:8000 \
  -p 5900:5900 \
  -e SAVISOR_API_KEY="savisor_live_secret_key_9812" \
  -e VNC_PASSWORD="savisorpass" \
  -e STORAGE_BACKEND="github" \
  -e GITHUB_TOKEN="ghp_yourGitHubPersonalAccessToken" \
  -e GITHUB_REPO="devffex/dataset" \
  -e GITHUB_BRANCH="main" \
  -e GITHUB_CDN_BASE_URL="https://cdn.jsdelivr.net/gh/devffex/dataset@main" \
  -e AUDIT_LOG_SINK="sqlite" \
  savisor-market-node:latest
```

---

### 3. Connecting via TigerVNC

To perform the one-time broker authentication inside the virtualized Wine MetaTrader 5 desktop:

```bash
# Connect using TigerVNC CLI
vncviewer localhost:5900
```
*(Or launch the **TigerVNC Viewer** GUI and enter `localhost:5900` or `127.0.0.1:5900`)*

1. **VNC Password**: When prompted, enter `savisorpass` (or the custom value configured in `VNC_PASSWORD`).
2. **Authenticate MT5**:
   - Go to `File -> Login to Trade Account`.
   - Enter your Broker **Login**, **Password**, and **Server**.
   - Check **Save password** and click **OK**.
   - Confirm connection in the bottom right corner (green/blue signal bars).
3. **Close VNC**: You can safely close TigerVNC. All further data operations are 100% automated by the API.

---

## 4. API Directory


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
