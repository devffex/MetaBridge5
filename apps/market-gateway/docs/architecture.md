# Architecture & System Design Manual

The **Savisor Market Node** is an autonomous market data collection, real-time in-flight **Candle 0** engine, and historical dataset pipeline designed for MetaTrader 5 broker terminals.

---

## 1. System Architecture Overview

```mermaid
flowchart TD
    subgraph Broker ["Broker Infrastructure"]
        TradeServer[("Broker Trade Server")]
    end

    subgraph ContainerNode ["Savisor Market Node (Docker Container)"]
        subgraph VirtualizationLayer ["Wine Virtualization & MT5 Daemon"]
            MT5Terminal["MetaTrader 5 Terminal (terminal64.exe)"]
            SafeLock["SafeMT5Lock (Mutual Exclusion Mutex)"]
            GRPCDaemon["MT5 Python gRPC Daemon (port 50051)"]
            XvfbDisplay["Xvfb Display :1 & x11vnc (port 5900)"]
        end

        subgraph GatewayLayer ["Market Gateway Service (port 8000)"]
            FastAPIServer["FastAPI Gateway & Auth Guard (X-API-Key)"]
            GRPCClient["TerminalGRPCClient (Channel Pooling, 64MB Limit)"]
            Candle0Engine["Candle0Manager (In-Flight Bar Aggregator)"]
            PipelineWorker["BackfillWorker (Chunked Sync Pipeline)"]
            ParquetExporter["Parquet & Compact JSON Exporter"]
            StorageFactory["StorageFactory (Strategy Pattern)"]
            AuditFactory["AuditLoggerFactory (Factory Pattern)"]
            WebSocketHub["WebSocket Connection Hub"]
        end

        subgraph LocalTelemetry ["Local Audit & Telemetry"]
            SQLiteWAL[("SQLite WAL DB (/tmp/savisor_traces.sqlite3)")]
        end
    end

    subgraph StorageLayer ["Global Storage & Multi-CDN Layer"]
        GitHubSink["GitHub Repo Sink (devffex/dataset)"]
        PurgeAPI["jsDelivr Instant Purge API"]
        JSDelivrCDN["jsDelivr Multi-CDN (Cloudflare + Fastly Edge)"]
        S3Storage[("Cloudflare R2 / AWS S3")]
    end

    subgraph Consumers ["Client Ecosystem"]
        ReactCharts["TradingView / Lightweight Charts (React/TS)"]
        TradingBots["Autonomous Python Trading Bots"]
        MLPipelines["DuckDB / Polars ML Pipelines"]
    end

    %% Internal Data Flow
    TradeServer <-->|"Live Ticks & Bar History"| MT5Terminal
    MT5Terminal <--> SafeLock
    SafeLock <--> GRPCDaemon
    GRPCDaemon <-->|"gRPC IPC (Port 50051)"| GRPCClient

    GRPCClient -->|"Poll Ticks (200ms)"| Candle0Engine
    Candle0Engine -->|"Broadcast In-Flight OHLCV"| WebSocketHub
    Candle0Engine -->|"On Period Rollover (M1..MN1)"| PipelineWorker

    GRPCClient -->|"Fetch Batch Chunks (25k Bars)"| PipelineWorker
    PipelineWorker --> ParquetExporter
    ParquetExporter --> StorageFactory

    StorageFactory -->|"Git Commit"| GitHubSink
    StorageFactory -->|"Direct S3 Upload"| S3Storage
    GitHubSink -->|"Trigger Edge Purge"| PurgeAPI
    PurgeAPI --> JSDelivrCDN
    GitHubSink --> JSDelivrCDN

    PipelineWorker -->|"Audit Event"| AuditFactory
    AuditFactory -->|"Microsecond Write"| SQLiteWAL

    FastAPIServer --> WebSocketHub
    FastAPIServer --> Candle0Engine
    FastAPIServer --> PipelineWorker

    %% Client Consumption Patterns
    JSDelivrCDN -->|"1. Fast Warmup (recent.json / history.parquet)"| ReactCharts
    WebSocketHub -->|"2. Sub-second Candle 0 Updates (WS)"| ReactCharts

    JSDelivrCDN -->|"1. Indicator Warmup (EMA, RSI, ATR)"| TradingBots
    WebSocketHub -->|"2. Live Market Ticks & Signals"| TradingBots

    JSDelivrCDN -->|"Scan & Query Parquet Partitions"| MLPipelines
```

---

## 2. Container Process Supervision Matrix

All container services are isolated and orchestrated via `supervisord` (`/etc/supervisord.conf`):

| Service | Process / Binary | Role | Port |
|---|---|---|---|
| **`xvfb`** | `Xvfb :1 -screen 0 1920x1080x16` | Headless virtual X11 display buffer for Wine. | Internal |
| **`x11vnc`** | `x11vnc -display :1 -rfbauth ...` | Remote desktop server for one-time broker setup. | `5900` |
| **`wine`** | `terminal64.exe /portable` | Native Windows MetaTrader 5 trading terminal. | Outbound |
| **`api`** | `grpc_server.py 50051` | Windows Python gRPC daemon with `SafeMT5Lock` (64MB message buffers). | `50051` (internal) |
| **`market-gateway`** | `uvicorn app.main:app --port 8000` | Linux Python REST API, WebSocket broadcaster & pipeline worker. | `8000` |

---

## 3. Thread Safety & Mutex Locking (`SafeMT5Lock`)

MetaTrader 5's native C-API and Python bindings are strictly single-threaded per process. Concurrent calls to `mt5.copy_rates_from_pos` or `mt5.symbol_info_tick` can corrupt terminal memory or cause segmentation faults.

To guarantee 100% thread safety:
* The internal Windows gRPC daemon wraps every MT5 library call inside `SafeMT5Lock` (a reentrant threading mutex).
* The Market Gateway manages symbol-specific asyncio locks (`_sync_locks[symbol]`) in `BackfillWorker` to prevent concurrent pipeline write operations on the same asset partition.

---

## 4. High-Throughput gRPC Buffer Architecture (64MB)

Broker catalogs for large multi-asset brokerages (containing thousands of currency pairs, crypto pairs, and equities) generate payloads exceeding 25MB of protobuf data.
* Both the gRPC Server (`docker/daemon/grpc_server.py`) and gRPC Client (`apps/market-gateway/src/grpc_client.py`) explicitly configure:
  ```python
  options = [
      ("grpc.max_send_message_length", 64 * 1024 * 1024),
      ("grpc.max_receive_message_length", 64 * 1024 * 1024),
  ]
  ```
* Prevents `RESOURCE_EXHAUSTED` payload errors when querying complete broker asset catalogs.

---

## 5. Network & Port Allocation

| Port | Protocol | Exposure | Description |
|---|---|---|---|
| `8000` | HTTP / WebSocket | Public / Reverse Proxy | FastAPI gateway, REST endpoints, and live WebSocket streaming. |
| `5900` | RFB / VNC | Localhost / Private VPN | TigerVNC remote desktop for initial broker account setup. |
| `50051` | gRPC over TCP | Container Internal | High-speed IPC bridge between Linux Python gateway and Windows Wine MT5. |
