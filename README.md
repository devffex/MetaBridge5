# Savisor Monorepo

Savisor is an algorithmic trading codebase organized as a monorepo. It uses a **Shared Base Image** architecture to build target-specific, standalone Docker containers, all based on Wine, VNC, and MetaTrader 5, while keeping individual images as lightweight and fast-building as possible.

---

## Architecture

```mermaid
graph TD
    classDef base fill:#efebe9,stroke:#5d4037,stroke-width:2px;
    classDef gateway fill:#e1f5fe,stroke:#0288d1,stroke-width:2px;
    classDef pipeline fill:#e8f5e9,stroke:#2e7d32,stroke-width:2px;
    classDef bot fill:#fff3e0,stroke:#ef6c00,stroke-width:2px;
    
    subgraph Base ["Base Image Construction"]
        DockerfileBase["docker/Dockerfile.base"] -->|docker build| BaseImage(("savisor-base:latest")):::base
    end

    subgraph Targets ["Standalone Deployment Targets"]
        BaseImage -->|FROM| DockerfileAPI["apps/market-gateway/Dockerfile"]
        BaseImage -->|FROM| DockerfilePipe["apps/data-pipeline/Dockerfile"]
        BaseImage -->|FROM| DockerfileBot["apps/trading-bot/Dockerfile"]
        
        DockerfileAPI -->|docker build| ImageAPI(("savisor-market-node:latest")):::gateway
        DockerfilePipe -->|docker build| ImagePipe(("savisor-pipeline:latest")):::pipeline
        DockerfileBot -->|docker build| ImageBot(("savisor-bot:latest")):::bot
    end

    subgraph Runtime ["Individual Standalone Runs"]
        ImageAPI -->|Run Standalone| ContainerAPI["Market Data & Pipeline Node<br/>(Exposes Port 8000 & 5900)"]:::gateway
        ImagePipe -->|Run Standalone| ContainerPipe["Data Pipeline Ingest Node<br/>(One-shot Run & Exit)"]:::pipeline
        ImageBot -->|Run Standalone| ContainerBot["Trading Bot Node<br/>(Persistent execution loop)"]:::bot
    end
```

### Key Concepts

* **Shared Base Image (`savisor-base`)**: Handles all heavy layers—Wine emulation, X Virtual Framebuffer (Xvfb), virtual display configuration, VNC setups, certificate synchronization, MetaTrader 5 terminal installations, and a Windows Python environment loaded with core packages (`numpy`, `pandas`, `MetaTrader5`).
* **Standalone Deployment targets**: Child Dockerfiles inherit `FROM savisor-base` and only inject their specific codebase, supervisord service parameters, and package requirements (e.g. `fastapi` in the Market Gateway, or machine learning libraries in the Bot).
* **Supervisord Inclusion**: The base image provides `/etc/supervisord.conf` with core virtualization layers. Child Dockerfiles mount their specific configuration under `/etc/supervisor/conf.d/*.conf` to start their specific Python scripts.

---

## MetaTrader 5 Interaction Modes

Savisor supports two distinct engineering approaches for interacting with the MetaTrader 5 instance running inside a container:

### Mode A: Batch / Bulk Ingestion Engine
* **Best for**: Mass Data Collection, Historical Backfill, ETL, CSV/Parquet Exports, and Disk-Heavy Writes.
* **High Throughput & Efficiency**: Optimized for volume over immediacy. It fetches large blocks of historical candles (e.g., 50,000 bars) and writes them to SQLite/CSV using bulk transactions (like SQLite WAL mode) to maximize disk I/O efficiency.
* **Stateless & Resilient**: Can be executed on demand, scheduled via cron/Airflow, or run in parallel per asset symbol without keeping long-running state in memory.
* **Resource Cleanup**: Starts up, executes the backfill job, flushes to disk, and cleanly exits or prunes temporary resources.

### Mode B: Persistent Event-Driven Daemon (gRPC / Streaming)
* **Best for**: Autonomous Trading Agents, Live Tick Monitoring, Order Execution, and Sub-second Market Reactions.
* **Ultra-Low Latency**: Keeps the Docker container, Wine MT5 instance, and gRPC server alive continuously in RAM. Eliminates process startup time and file I/O overhead.
* **Event-Driven & In-Memory**: Streams live ticks/bars directly to the agent over persistent gRPC or WebSocket channels. Live market state remains in memory (RAM) so the agent can evaluate trading signals and place orders in milliseconds.
* **Bi-directional Control**: Allows the agent to receive live tick events and immediately push execution commands (`BUY`, `SELL`, `MODIFY_STOP_LOSS`) back through the persistent connection without writing to disk first.

---

## Documentation & Client Integration Guides
* 📖 **[Client API & Integration Guide](file:///home/julio/Work/savisor/savisor-node/docs/client_api.md)** — Complete guide for connecting React/TradingView charts, Python bots, DuckDB/Polars ML pipelines, REST snapshot endpoints, and live WebSocket streaming.
* 📦 **[Base Image Optimization](file:///home/julio/Work/savisor/savisor-node/docs/base_image_optimization.md)** — Wine, font caching, and Python binary insulation specs.
* ⚡ **[MetaTrader Lightweight Tuning](file:///home/julio/Work/savisor/savisor-node/docs/metatrader_lightweight.md)** — Resource throttling and headless memory management.

---

## Directory Layout

```text
savisor-monorepo/
├── docker/
│   ├── supervisord/             # Shared startup scripts (entrypoint, dismiss popups)
│   ├── import_certs.py          # Wine cryptographic CAs synchronizer
│   ├── supervisord.conf         # Base supervisor config
│   └── Dockerfile.base          # Heavy Wine + MT5 + Python base image
│
├── apps/
│   ├── market-gateway/          # Real-time Market Feed & Pipeline Node
│   │   ├── src/                 # Engine (Candle 0), Pipeline (Backfill/Parquet), Storage, Telemetry
│   │   ├── tests/               # 12-Perspective Unit Test Suite
│   │   ├── supervisord.conf     # Runs FastAPI uvicorn server
│   │   └── Dockerfile           
│   │
│   ├── data-pipeline/           # Ingest Data Pipeline target
│   │   ├── src/                 # Ingest main scripts
│   │   ├── supervisord.conf     # Runs one-shot pipeline and exits container
│   │   └── Dockerfile           
│   │
│   └── trading-bot/             # Algorithmic Trading Bot target
│       ├── src/                 # Trading bot loops
│       ├── supervisord.conf     # Runs persistent bot daemon
│       └── Dockerfile           
│
├── MetaTrader5/                 # Portable MT5 binary (host-supplied)
├── docker-compose.yml           # Production Docker Compose orchestration
├── Makefile                     # Build & run automations
└── README.md
```

---

## Quick Start

### 1. Supply MetaTrader 5
1. Install MetaTrader 5 on a Windows machine.
2. Run once in portable mode (`C:\MetaTrader5\terminal64.exe /portable`) and log in to your broker.
3. Clean up cache files to avoid connection conflicts: delete `MetaTrader5/Config/terminal.lic` and `MetaTrader5/Config/accounts.dat`.
4. Copy the entire `C:\MetaTrader5` folder to this project's root as `MetaTrader5/`.

### 2. Building & Running the Docker Images Locally

> [!IMPORTANT]
> **Build Locally First (Avoid "pull access denied")**:
> The `savisor-market-node:latest` image is built locally within this monorepo and is **not published on public Docker Hub**.
> If you run `docker run savisor-market-node:latest` before building, Docker will attempt to pull the image from Docker Hub and fail with `pull access denied`.
>
> You must build the images locally from the **monorepo root directory** using one of the two options below:

#### Option 1: Using the Makefile (Two-Step Local Build - Recommended)
Run these commands from the monorepo root:
```bash
# Step 1: Build the shared Wine + MT5 base image first
make build-base

# Step 2: Build the standalone market node image
make build-market-node

# Step 3: Run the market node container
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

#### Option 2: Using Docker Compose (Simplest Single-Command Build & Run)
Ensure `apps/market-gateway/.env` is configured, then from the monorepo root run:
```bash
# Automatically builds and starts the container in one command:
docker compose up -d --build

# Follow live container logs:
docker compose logs -f
```

---

## Operational Workflow: Manual vs. Automated Operations

> [!IMPORTANT]
> **Zero Manual Chart Clicking Required**:
> You do **NOT** need to open MetaTrader 5 chart windows, scroll through historical bars, or manually click on `M1`, `M5`, `H1`, `D1` timeframe buttons to download broker history.
>
> The MetaTrader 5 terminal daemon automatically communicates with the broker's trade servers and downloads requested history in the background. Once logged into your broker account, **all further operations (symbol provisioning, multi-timeframe backfilling, Parquet export, CDN syncing, cache purging, and sub-second tick streaming) are 100% automated via REST and WebSocket APIs**.

### Operational Breakdown

| Operation | Mode | How It Works |
|---|---|---|
| **Broker Account Login** | **One-Time Setup** | Connect once via VNC (`localhost:5900`, password: `savisorpass`) to log in to your broker account, or pre-authenticate in the portable `MetaTrader5/` directory before building. |
| **Asset Watchlist Activation** | **100% Automated** | Call `POST /api/v1/symbols/active` with `{"symbol": "EURUSD"}`. The node activates the symbol in the broker's Market Watch. |
| **Broker History Downloads** | **100% Automated** | `BackfillWorker` queries MT5 via gRPC. The terminal daemon automatically downloads missing history from the broker in the background. |
| **Multi-Timeframe Generation (`M1`..`MN1`)** | **100% Automated** | Automatically generates datasets across all timeframes without opening chart windows. |
| **Parquet & Compact JSON Exports** | **100% Automated** | Compresses historical bars into Apache Parquet (`history.parquet`) and compact JSON (`recent.json`). |
| **Multi-CDN Sync & Edge Cache Purge** | **100% Automated** | Commits datasets to GitHub (`devffex/dataset`) and purges the jsDelivr edge cache automatically. |
| **Live Tick & Candle 0 Streaming** | **100% Automated** | Streams live ticks and aggregates the active forming Candle 0 over WebSockets (`WS /api/v1/market/ws/{symbol}`). |

---

## Running Locally with GitHub Storage (jsDelivr Multi-CDN) & SQLite Database


You can run the **Savisor Market Data Node** locally with:
- **Storage Target**: **GitHub Public Repository + jsDelivr Multi-CDN** (`devffex/dataset`) for high-availability worldwide dataset distribution with $0 bandwidth cost, multi-CDN edge failover (Cloudflare + Fastly + BunnyCDN), and instant cache invalidation on candle closures.
- **Telemetry & Audit Database**: **Internal SQLite in WAL mode** (zero-overhead microsecond audit logging inside `/home/wine/data/traces.sqlite3`).

### 1. Prerequisites
1. A GitHub Personal Access Token (PAT) with `repo` scope (or fine-grained token with `Contents: Read and write`).
2. A GitHub repository to host the datasets (e.g. `devffex/dataset`).

### 2. Configuration (`apps/market-gateway/.env`)
Create/update `apps/market-gateway/.env`:

```ini
SAVISOR_API_KEY=savisor_live_secret_key_9812
VNC_PASSWORD=savisorpass

# 1. Storage Backend: GitHub + jsDelivr Multi-CDN
STORAGE_BACKEND=github
GITHUB_TOKEN=ghp_yourGitHubPersonalAccessTokenHere
GITHUB_REPO=devffex/dataset
GITHUB_BRANCH=main
GITHUB_CDN_BASE_URL=https://cdn.jsdelivr.net/gh/devffex/dataset@main

# 2. Audit & Telemetry Database: Local SQLite in WAL mode
AUDIT_LOG_SINK=sqlite

# Optional: Run with Mock MT5 data for testing without live broker connection
METAFORGE_MOCK_MT5=1
```

### 3. Launch the Node

#### Option A: Using Docker Compose
```bash
# Build and start the container in background
docker compose up -d

# Follow live container logs
docker compose logs -f
```

#### Option B: Using Direct Docker Run
```bash
docker run -d --name savisor-market-node \
  -p 8000:8000 \
  -p 5900:5900 \
  -e SAVISOR_API_KEY="savisor_live_secret_key_9812" \
  -e VNC_PASSWORD="savisorpass" \
  -e STORAGE_BACKEND="github" \
  -e GITHUB_TOKEN="ghp_yourGitHubPersonalAccessTokenHere" \
  -e GITHUB_REPO="devffex/dataset" \
  -e GITHUB_BRANCH="main" \
  -e GITHUB_CDN_BASE_URL="https://cdn.jsdelivr.net/gh/devffex/dataset@main" \
  -e AUDIT_LOG_SINK="sqlite" \
  -e METAFORGE_MOCK_MT5="1" \
  savisor-market-node:latest
```

---

### 4. Verify & Trigger Data Ingestion

#### A. Verify Health and Telemetry Probes
```bash
# Liveness Probe
curl -i http://localhost:8000/health

# Readiness Probe
curl -i http://localhost:8000/ready

# Prometheus Telemetry Metrics
curl http://localhost:8000/metrics
```

#### B. Provision an Asset & Trigger Auto-Backfill to GitHub
```bash
curl -i -X POST http://localhost:8000/api/v1/symbols/active \
  -H "X-API-Key: savisor_live_secret_key_9812" \
  -H "Content-Type: application/json" \
  -d '{
    "symbol": "EURUSD",
    "auto_backfill": true,
    "candle_count": 5000
  }'
```
This triggers the `BackfillWorker` to:
1. Pull 5,000 historical bars across timeframes (`M1` to `MN1`) from MT5.
2. Compress into Apache Parquet (`data/EURUSD/H1/history.parquet`) and compact JSON (`data/EURUSD/H1/recent.json`).
3. Commit the datasets directly to `devffex/dataset` on branch `main`.
4. Trigger the jsDelivr edge purge API (`https://purge.jsdelivr.net/...`) for instant cache invalidation.
5. Generate `data/EURUSD/manifest.json`.

#### C. Inspect Generated Datasets on jsDelivr Global Multi-CDN
* **Parquet History**: `https://cdn.jsdelivr.net/gh/devffex/dataset@main/data/EURUSD/H1/history.parquet`
* **Recent 500 Candles JSON**: `https://cdn.jsdelivr.net/gh/devffex/dataset@main/data/EURUSD/H1/recent.json`
* **Asset Manifest**: `https://cdn.jsdelivr.net/gh/devffex/dataset@main/data/EURUSD/manifest.json`
* **GitHub Repository View**: `https://github.com/devffex/dataset/tree/main/data/EURUSD`

#### D. Query Internal SQLite Audit & Trace Logs
```bash
curl -i -H "X-API-Key: savisor_live_secret_key_9812" \
  "http://localhost:8000/api/v1/telemetry/traces?symbol=EURUSD&limit=10"
```

#### E. Stream Real-Time Candle 0 & Live Ticks
```bash
# Instant in-flight Candle 0 snapshot (M1 timeframe)
curl -i -H "X-API-Key: savisor_live_secret_key_9812" \
  "http://localhost:8000/api/v1/market/candle0?symbol=EURUSD&timeframe=M1"

# Connect to WebSocket stream (using wscat or frontend chart)
wscat -c ws://localhost:8000/api/v1/market/ws/EURUSD
```


---

## Local Development & Unit Tests

API logic, tests, and formatting are managed using `uv` inside the market-gateway app directory:

```bash
# Sync local virtual environment with all dependency groups
uv sync --project apps/market-gateway --all-groups

# Run linter and formatter checks
uv run --project apps/market-gateway ruff check apps/market-gateway/src apps/market-gateway/tests
uv run --project apps/market-gateway ruff format apps/market-gateway/src apps/market-gateway/tests

# Run the 12-Perspective Unit Test Suite (28 tests)
PYTHONPATH=apps/market-gateway uv run --project apps/market-gateway pytest apps/market-gateway/tests -v
```
