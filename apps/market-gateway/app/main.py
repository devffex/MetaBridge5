import asyncio
from datetime import datetime, timedelta, timezone
import logging
import os
from pathlib import Path

from cachetools import TTLCache
from fastapi import (
    BackgroundTasks,
    Depends,
    FastAPI,
    Header,
    HTTPException,
    Query,
    Response,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
)
from pydantic import BaseModel, Field
from starlette.responses import StreamingResponse

from app.engine.candle0_manager import Candle0Manager
from app.grpc_client import TerminalGRPCClient
from app.pipeline.backfill_worker import TIMEFRAME_MAP, BackfillWorker
from app.pipeline.health_monitor import evaluate_pipeline_health
from app.storage.base import StorageBackend
from app.storage.factory import StorageFactory
from app.telemetry.base import AuditRecord, AuditSink
from app.telemetry.event_broadcaster import broadcaster
from app.telemetry.factory import AuditLoggerFactory

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] [%(name)s]: %(message)s")
logger = logging.getLogger("market_gateway")

# Prometheus Metrics
TICKS_PROCESSED_TOTAL = Counter("metabridge5_ticks_processed_total", "Total ticks processed", ["symbol"])
CANDLE0_UPDATES_TOTAL = Counter(
    "metabridge5_candle0_updates_total", "Total Candle 0 updates computed", ["symbol", "timeframe"]
)
CANDLE0_CLOSES_TOTAL = Counter(
    "metabridge5_candle0_closes_total", "Total candles closed and rolled up", ["symbol", "timeframe"]
)
WS_CONNECTIONS_GAUGE = Gauge("metabridge5_ws_active_connections", "Active WebSocket connections", ["symbol"])
BACKFILL_DURATION_SECONDS = Histogram(
    "metabridge5_backfill_duration_seconds", "Duration of backfill operations in seconds", ["symbol"]
)
TICK_AGE_SECONDS = Gauge("metabridge5_symbol_tick_age_seconds", "Seconds elapsed since last price tick", ["symbol"])
STUCK_JOBS_GAUGE = Gauge("metabridge5_stuck_pipeline_jobs_count", "Number of stuck non-terminal pipeline jobs")

from contextlib import asynccontextmanager

# Singletons & Managers
grpc_client: TerminalGRPCClient | None = None
storage_backend: StorageBackend | None = None
candle_manager: Candle0Manager | None = None
backfill_worker: BackfillWorker | None = None
audit_sink: AuditSink | None = None

# In-memory caches
rates_cache = TTLCache(maxsize=1000, ttl=5)
active_poll_tasks: dict[str, asyncio.Task] = {}
symbol_subscriptions: dict[str, set[WebSocket]] = {}
ws_lock = asyncio.Lock()
fetch_locks: dict[tuple, asyncio.Lock] = {}
fetch_locks_lock = asyncio.Lock()


async def get_fetch_lock(cache_key: tuple) -> asyncio.Lock:
    async with fetch_locks_lock:
        if cache_key not in fetch_locks:
            fetch_locks[cache_key] = asyncio.Lock()
        return fetch_locks[cache_key]


# ---------------------------------------------------------
# Real-Time WebSocket Streaming Worker (Candle 0 & Live Ticks)
# ---------------------------------------------------------
async def poll_ticks_loop(symbol: str):
    """
    Background worker that polls MT5 ticks, feeds Candle0Manager,
    and broadcasts live tick + Candle 0 states to subscribers.
    """
    logger.info(f"Starting background tick & Candle 0 poll loop for {symbol}...")
    last_tick_time = 0
    last_tick_bid = 0.0

    try:
        while True:
            try:
                if grpc_client:
                    tick = grpc_client.get_symbol_info_tick(symbol)
                    if tick:
                        tick_time = tick.get("time", 0)
                        bid = tick.get("bid", 0.0)

                        if tick_time != last_tick_time or bid != last_tick_bid:
                            last_tick_time = tick_time
                            last_tick_bid = bid
                            TICKS_PROCESSED_TOTAL.labels(symbol=symbol).inc()

                            # Update in-memory Candle 0 state across all timeframes
                            candle0_states = {}
                            if candle_manager:
                                candle0_states = await candle_manager.process_tick(symbol, tick)

                            # Broadcast to active WebSockets
                            websockets = symbol_subscriptions.get(symbol, set())
                            if websockets:
                                payload = {
                                    "type": "tick",
                                    "symbol": symbol,
                                    "time": tick_time,
                                    "bid": bid,
                                    "ask": tick.get("ask", 0.0),
                                    "last": tick.get("last", 0.0),
                                    "volume": tick.get("volume", 0),
                                    "candle0": {tf: state.to_compact_array() for tf, state in candle0_states.items()},
                                }
                                async with ws_lock:
                                    dead_ws = set()
                                    for ws in list(websockets):
                                        try:
                                            await ws.send_json(payload)
                                        except Exception:
                                            dead_ws.add(ws)
                                    if dead_ws:
                                        websockets.difference_update(dead_ws)
                                        WS_CONNECTIONS_GAUGE.labels(symbol=symbol).set(len(websockets))

            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.error(f"Error in tick polling loop for {symbol}: {e}")

            # 200ms sleep for high-frequency sub-second tick tracking
            await asyncio.sleep(0.20)

    except asyncio.CancelledError:
        pass
    finally:
        logger.info(f"Stopped background tick poll loop for {symbol}.")


# ---------------------------------------------------------
# Security Dependency
# ---------------------------------------------------------
def verify_api_key(x_api_key: str | None = Header(None)):
    expected_key = os.environ.get("METABRIDGE5_API_KEY")
    if expected_key and x_api_key != expected_key:
        raise HTTPException(status_code=401, detail="Invalid or missing X-API-Key header")
    return x_api_key


# ---------------------------------------------------------
# Pydantic Schemas
# ---------------------------------------------------------
class SymbolProvisionRequest(BaseModel):
    symbol: str = Field(..., description="Broker symbol to activate e.g. 'EURUSD'")
    auto_backfill: bool = Field(True, description="Whether to trigger initial historical backfill upon activation")
    candle_count: int = Field(100000, description="Max candles to backfill if days/dates are not specified")
    days: int | None = Field(None, description="Number of past days to extract e.g. 30, 90, 365")
    timeframes: list[str] | None = Field(None, description="List of timeframes e.g. ['M1', 'M5', 'H1', 'D1']")


class SymbolProvisionResponse(BaseModel):
    symbol: str
    success: bool
    message: str
    backfill_status: str | None = None


class BackfillRequest(BaseModel):
    symbol: str | None = Field(None, description="Single asset symbol (e.g. 'EURUSD') or 'ALL' / '*' for all assets")
    symbols: list[str] | None = Field(None, description="Explicit list of asset symbols e.g. ['EURUSD', 'GBPUSD']")
    all_symbols: bool = Field(False, description="If true, backfills all active symbols or all broker catalog symbols")
    source: str = Field("active", description="Asset source when all_symbols is True: 'active' (Market Watch) or 'broker' (entire catalog)")
    timeframes: list[str] | None = Field(None, description="List of timeframes e.g. ['M1', 'M5', 'H1', 'D1']. Defaults to all 9 supported.")
    candle_count: int = Field(100000, description="Max candles to fetch per timeframe if date range is not specified")
    days: int | None = Field(None, description="Number of past days to extract e.g. 30, 90, 365. Automatically computes date_from and date_to.")
    date_from: str | None = Field(None, description="ISO 8601 start date (e.g. '2024-01-01T00:00:00Z')")
    date_to: str | None = Field(None, description="ISO 8601 end date (e.g. '2024-12-31T23:59:59Z')")


class PipelineControlRequest(BaseModel):
    action: str = Field("pause", description="'pause' or 'resume'")
    scope: str = Field("all", description="'all', 'symbols', or 'exclude'")
    symbols: list[str] = Field(default_factory=list, description="Target asset symbols")


@asynccontextmanager
async def lifespan(app: FastAPI):
    global grpc_client, storage_backend, candle_manager, backfill_worker, audit_sink
    grpc_client = TerminalGRPCClient()
    storage_backend = StorageFactory.get_backend()
    audit_sink = AuditLoggerFactory.get_sink()
    candle_manager = Candle0Manager()
    backfill_worker = BackfillWorker(
        grpc_client=grpc_client,
        storage_backend=storage_backend,
        audit_sink=audit_sink,
    )

    # Register incremental sync callback when candle closes
    candle_manager.register_close_callback(backfill_worker.handle_candle_close)
    if audit_sink:
        audit_sink.record(AuditRecord(component="gateway", event="node_started", status="info"))
    logger.info("MetaBridge5 Market Gateway started successfully.")

    # Auto-provision boot symbols if configured via METABRIDGE5_SYMBOLS
    boot_symbols_env = os.environ.get("METABRIDGE5_SYMBOLS", "").strip()
    auto_backfill_start = os.environ.get("METABRIDGE5_AUTO_BACKFILL_ON_START", "false").lower() in ("true", "1", "yes")

    symbols_to_init: list[str] = []
    if boot_symbols_env:
        if boot_symbols_env.upper() in ("*", "ALL", "ALL_ACTIVE"):
            try:
                active = grpc_client.get_symbols(selected_only=True)
                symbols_to_init = [s.get("name") for s in active if s.get("name")]
            except Exception as e:
                logger.warning(f"Failed to query active symbols for startup: {e}")
        else:
            symbols_to_init = [s.strip().upper() for s in boot_symbols_env.split(",") if s.strip()]

    for sym in symbols_to_init:
        try:
            grpc_client.select_symbol(sym, True)
            if sym not in active_poll_tasks:
                task = asyncio.create_task(poll_ticks_loop(sym))
                active_poll_tasks[sym] = task
                logger.info(f"Initialized live tick streaming for startup symbol {sym}")
            if auto_backfill_start and backfill_worker:
                asyncio.create_task(backfill_worker.run_initial_backfill(symbol=sym))
                logger.info(f"Queued startup historical backfill for {sym}")
        except Exception as e:
            logger.warning(f"Could not initialize startup symbol {sym}: {e}")

    yield
    # Shutdown logic
    for symbol, task in active_poll_tasks.items():
        logger.info(f"Cancelling poll task for {symbol}...")
        task.cancel()
    if grpc_client:
        grpc_client.close()
    if audit_sink:
        audit_sink.record(AuditRecord(component="gateway", event="node_stopped", status="info"))
        audit_sink.close()
    logger.info("MetaBridge5 Market Gateway stopped.")


app = FastAPI(
    title="MetaBridge5 Market Gateway",
    description="Autonomous real-time market data feed, Candle 0 engine, and historical data pipeline for MetaTrader 5",
    version="2.0.0",
    lifespan=lifespan,
)


# Enable CORS for frontend integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve generated parquet and JSON analytics datasets
os.makedirs("/tmp/metabridge5_data", exist_ok=True)
app.mount("/static", StaticFiles(directory="/tmp/metabridge5_data"), name="static")


@app.get("/metrics")
def metrics():
    """Prometheus metrics scrape endpoint."""
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.get("/health")
def health_check():
    """Liveness probe."""
    if not grpc_client:
        return {"status": "error", "message": "Client not initialized"}
    daemon_health = grpc_client.get_health()
    return {
        "status": "ok" if daemon_health.get("status") == "ok" else "degraded",
        "node": "metabridge5-node",
        "storage": type(storage_backend).__name__ if storage_backend else "none",
        "daemon": daemon_health,
    }


@app.get("/ready")
def readiness_check():
    """Readiness probe checking terminal connectivity and storage."""
    if not grpc_client or not storage_backend:
        raise HTTPException(status_code=503, detail="Services not fully initialized")
    daemon_health = grpc_client.get_health()
    if daemon_health.get("status") != "ok":
        raise HTTPException(status_code=503, detail="gRPC daemon not ready")
    return {"status": "ready"}


@app.get("/api/v1/telemetry/traces", dependencies=[Depends(verify_api_key)])
def query_telemetry_traces(
    limit: int = Query(50, ge=1, le=500, description="Max traces to retrieve"),
    symbol: str | None = Query(None, description="Filter by symbol e.g. EURUSD"),
    event: str | None = Query(None, description="Filter by event name e.g. backfill_completed"),
    component: str | None = Query(None, description="Filter by component e.g. pipeline"),
):
    """Queries audit and distributed trace records from the active audit sink (SQLite WAL / Composite)."""
    if not audit_sink:
        return {"traces": []}
    records = audit_sink.query(limit=limit, symbol=symbol, event=event, component=component)
    return {
        "sink": type(audit_sink).__name__,
        "count": len(records),
        "traces": records,
    }


@app.get("/api/v1/terminal/logs", dependencies=[Depends(verify_api_key)])
def get_terminal_logs(
    lines: int = Query(100, ge=1, le=2000, description="Number of recent log lines to retrieve"),
    date: str | None = Query(None, description="Optional log date formatted as YYYYMMDD (default: latest)"),
):
    """
    Retrieves and tails raw MetaTrader 5 daily platform journal logs.
    """
    log_dir = Path("/home/wine/.wine/drive_c/mt5-data/logs")
    if not log_dir.exists():
        log_dir = Path("/opt/metabridge5/MetaTrader5/logs")
    if not log_dir.exists():
        log_dir = Path("/home/wine/.wine/drive_c/MetaTrader5/logs")
    if not log_dir.exists():
        log_dir = Path("MetaTrader5/logs")

    if not log_dir.exists():
        return {"logs": [], "message": "MetaTrader 5 log directory not found"}

    if date:
        target_file = log_dir / f"{date}.log"
        if not target_file.exists():
            raise HTTPException(status_code=404, detail=f"Log file for date {date} not found")
        files = [target_file]
    else:
        files = sorted(log_dir.glob("*.log"), key=lambda f: f.stat().st_mtime, reverse=True)

    if not files:
        return {"logs": [], "message": "No log files available"}

    latest_file = files[0]
    try:
        with open(latest_file, "rb") as f:
            raw = f.read()
        try:
            content = raw.decode("utf-16-le")
        except UnicodeDecodeError:
            content = raw.decode("utf-8", errors="replace")

        log_lines = [line.strip() for line in content.splitlines() if line.strip()]
        tailed_lines = log_lines[-lines:] if len(log_lines) > lines else log_lines
        return {
            "file": latest_file.name,
            "total_lines": len(log_lines),
            "returned_lines": len(tailed_lines),
            "lines": tailed_lines,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error reading log file {latest_file.name}: {e!s}")


# ---------------------------------------------------------
# Real-Time Candle 0 Endpoints
# ---------------------------------------------------------
@app.get("/api/v1/market/candle0", dependencies=[Depends(verify_api_key)])
@app.get("/api/v1/chart/candle0", dependencies=[Depends(verify_api_key)], include_in_schema=False)
def get_candle0_snapshot(
    symbol: str = Query(..., description="Symbol e.g. EURUSD"),
    timeframe: str = Query("M1", description="Timeframe e.g. M1, M5, H1"),
):
    """Returns the instantaneous, in-flight Candle 0 state for the requested asset and timeframe."""
    if not candle_manager:
        raise HTTPException(status_code=500, detail="Candle manager uninitialized")
    state = candle_manager.get_candle0(symbol, timeframe)
    if not state:
        raise HTTPException(
            status_code=404, detail=f"No active Candle 0 found for {symbol} {timeframe}. Ensure symbol is provisioned."
        )
    return state.to_dict()


@app.get("/api/v1/market/candle0/all", dependencies=[Depends(verify_api_key)])
@app.get("/api/v1/chart/candle0/all", dependencies=[Depends(verify_api_key)], include_in_schema=False)
def get_all_candle0_snapshots(
    symbol: str = Query(..., description="Symbol e.g. EURUSD"),
):
    """Returns active Candle 0 states across all timeframes for the specified symbol."""
    if not candle_manager:
        raise HTTPException(status_code=500, detail="Candle manager uninitialized")
    return candle_manager.get_all_candle0(symbol)


# ---------------------------------------------------------
# Data Pipeline & Backfill Endpoints
# ---------------------------------------------------------
@app.post("/api/v1/pipeline/backfill", dependencies=[Depends(verify_api_key)])
async def trigger_backfill(
    payload: BackfillRequest,
    background_tasks: BackgroundTasks,
):
    """Triggers an on-demand historical backfill for single, multiple, or all available assets across timeframes."""
    if not backfill_worker:
        raise HTTPException(status_code=500, detail="Backfill worker uninitialized")

    # 1. Resolve Target Asset Symbols
    target_symbols: list[str] = []
    if payload.all_symbols or (payload.symbol and payload.symbol.upper() in ("ALL", "*")):
        if payload.source == "broker":
            broker_syms = grpc_client.get_symbols() if grpc_client else []
            target_symbols = [s.get("name") for s in broker_syms if s.get("name")]
        else:
            active_syms = grpc_client.get_symbols(selected_only=True) if grpc_client else []
            target_symbols = [s.get("name") for s in active_syms if s.get("name")]
    elif payload.symbols:
        target_symbols = [s.strip().upper() for s in payload.symbols if s.strip()]
    elif payload.symbol:
        target_symbols = [payload.symbol.strip().upper()]
    else:
        # Default to all active symbols currently enabled in MT5 Market Watch
        active_syms = grpc_client.get_symbols(selected_only=True) if grpc_client else []
        target_symbols = [s.get("name") for s in active_syms if s.get("name")]

    if not target_symbols:
        raise HTTPException(
            status_code=400,
            detail="No symbols resolved for backfill. Please specify 'symbol', 'symbols', or ensure active symbols exist in Market Watch.",
        )

    # 2. Resolve Date Range / Relative Days
    resolved_date_from = payload.date_from
    resolved_date_to = payload.date_to
    if payload.days and payload.days > 0:
        now = datetime.now(timezone.utc)
        resolved_date_to = payload.date_to or now.strftime("%Y-%m-%dT%H:%M:%SZ")
        resolved_date_from = (now - timedelta(days=payload.days)).strftime("%Y-%m-%dT%H:%M:%SZ")

    resolved_timeframes = payload.timeframes or backfill_worker.timeframes

    # 3. Queue Background Ingestion Tasks
    async def _do_backfill():
        for sym in target_symbols:
            with BACKFILL_DURATION_SECONDS.labels(symbol=sym).time():
                await backfill_worker.run_initial_backfill(
                    symbol=sym,
                    timeframes=resolved_timeframes,
                    candle_count=payload.candle_count,
                    date_from=resolved_date_from,
                    date_to=resolved_date_to,
                )

    background_tasks.add_task(_do_backfill)
    return {
        "status": "triggered",
        "symbols": target_symbols,
        "total_symbols": len(target_symbols),
        "timeframes": resolved_timeframes,
        "days": payload.days,
        "date_from": resolved_date_from,
        "date_to": resolved_date_to,
        "candle_count": payload.candle_count if not (resolved_date_from and resolved_date_to) else None,
        "message": f"Historical backfill queued for {len(target_symbols)} asset(s) across {len(resolved_timeframes)} timeframe(s).",
    }


@app.post("/api/v1/pipeline/pause", dependencies=[Depends(verify_api_key)])
def pause_pipeline(symbol: str | None = Query(None, description="Optional symbol to pause individually")):
    """Pauses historical data extraction and storage pushes globally or for a specific symbol."""
    if not backfill_worker:
        raise HTTPException(status_code=500, detail="Backfill worker uninitialized")
    res = backfill_worker.pause(symbol)
    return {
        "status": "paused",
        **res,
        "message": f"Pipeline ingestion paused for {symbol.upper() if symbol else 'all symbols'}.",
    }


@app.post("/api/v1/pipeline/resume", dependencies=[Depends(verify_api_key)])
def resume_pipeline(symbol: str | None = Query(None, description="Optional symbol to resume individually")):
    """Resumes historical data extraction and storage pushes globally or for a specific symbol."""
    if not backfill_worker:
        raise HTTPException(status_code=500, detail="Backfill worker uninitialized")
    res = backfill_worker.resume(symbol)
    return {
        "status": "active",
        **res,
        "message": f"Pipeline ingestion resumed for {symbol.upper() if symbol else 'all symbols'}.",
    }


@app.post("/api/v1/pipeline/control", dependencies=[Depends(verify_api_key)])
def control_pipeline(payload: PipelineControlRequest):
    """
    Executes bulk or exclusionary pause/resume ingestion operations.
    Supports scopes: 'all', 'symbols', or 'exclude' (e.g. ingest ONLY USDJPY and pause others).
    """
    if not backfill_worker:
        raise HTTPException(status_code=500, detail="Backfill worker uninitialized")
    try:
        active_syms = (
            [s.get("name") for s in grpc_client.get_symbols(selected_only=True) if s.get("name")] if grpc_client else []
        )
    except Exception:
        active_syms = []

    try:
        res = backfill_worker.bulk_control(
            action=payload.action,
            scope=payload.scope,
            symbols=payload.symbols,
            active_symbols=active_syms,
        )
        return res
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/v1/pipeline/status", dependencies=[Depends(verify_api_key)])
def get_pipeline_status(symbol: str | None = Query(None)):
    """Inspects backfill worker status registry and granular active/paused states."""
    if not backfill_worker:
        raise HTTPException(status_code=500, detail="Backfill worker uninitialized")
    try:
        active_names = (
            [s.get("name") for s in grpc_client.get_symbols(selected_only=True) if s.get("name")] if grpc_client else []
        )
    except Exception:
        active_names = []

    paused_syms = backfill_worker.get_paused_symbols()
    if symbol:
        sym = symbol.upper()
        symbol_status = backfill_worker.status_registry.get(sym, {"status": "not_found"})
        return {
            "symbol": sym,
            "global_paused": backfill_worker.global_paused,
            "symbol_paused": backfill_worker.is_symbol_paused(sym),
            "status": symbol_status,
        }
    return {
        "global_paused": backfill_worker.global_paused,
        "paused_symbols": paused_syms,
        "active_symbols": active_names,
        "registry": backfill_worker.status_registry,
    }


@app.get("/api/v1/pipeline/interval", dependencies=[Depends(verify_api_key)])
def get_pipeline_sync_interval():
    """Returns the active dataset synchronization interval and supported timeframe intervals."""
    if not backfill_worker:
        raise HTTPException(status_code=500, detail="Backfill worker uninitialized")
    return backfill_worker.get_sync_interval()


@app.post("/api/v1/pipeline/interval", dependencies=[Depends(verify_api_key)])
def update_pipeline_sync_interval(interval: str = Query(..., description="Sync interval (e.g. 5m, 15m, 1h, 4h, 1d, 1w, 1mo or M5..MN1)")):
    """Updates the dataset synchronization interval at runtime."""
    if not backfill_worker:
        raise HTTPException(status_code=500, detail="Backfill worker uninitialized")
    try:
        updated = backfill_worker.set_sync_interval(interval)
        return {
            "status": "success",
            "active_sync_interval": updated,
            "message": f"Dataset sync interval updated to {updated}.",
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/v1/pipeline/health", dependencies=[Depends(verify_api_key)])
def get_pipeline_health():
    """
    Pure-verdict health evaluation: checks price feed freshness and catches stuck pipeline jobs.
    Adopted from the observe-only health monitor architecture in cifra-connectors.
    """
    if not backfill_worker:
        raise HTTPException(status_code=500, detail="Backfill worker uninitialized")
    try:
        active_syms = grpc_client.get_symbols(selected_only=True) if grpc_client else []
    except Exception:
        active_syms = []

    return evaluate_pipeline_health(active_syms, backfill_worker.status_registry)


@app.get("/api/v1/telemetry/stream")
async def stream_telemetry():
    """
    Real-time Server-Sent Events (SSE) stream for live pipeline and candle telemetry.
    Yields NDJSON payloads for every candle rollup, chunk fetch, and pause/resume event.
    """
    return StreamingResponse(
        broadcaster.subscribe(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ---------------------------------------------------------
# Historical Rates (Candles from MT5 Cache)
# ---------------------------------------------------------
@app.get("/api/v1/market/rates", dependencies=[Depends(verify_api_key)])
@app.get("/api/v1/chart/rates", dependencies=[Depends(verify_api_key)], include_in_schema=False)
async def get_chart_rates(
    symbol: str = Query(..., description="Financial asset symbol e.g., EURUSD"),
    timeframe: str = Query("H1", description="Timeframe e.g. M1, M5, H1, D1"),
    count: int = Query(500, ge=1, le=10000, description="Number of candles to retrieve"),
    start_pos: int = Query(0, ge=0, description="Starting bar index (0 represents the latest bar)"),
):
    tf_val = TIMEFRAME_MAP.get(timeframe.upper())
    if not tf_val:
        raise HTTPException(
            status_code=400, detail=f"Invalid timeframe '{timeframe}'. Supported: {list(TIMEFRAME_MAP.keys())}"
        )

    cache_key = (symbol, tf_val, start_pos, count)
    if cache_key in rates_cache:
        return rates_cache[cache_key]

    lock = await get_fetch_lock(cache_key)
    async with lock:
        if cache_key in rates_cache:
            return rates_cache[cache_key]

        try:
            rates = await asyncio.to_thread(grpc_client.get_rates_from_pos, symbol, tf_val, start_pos, count)
            compact_rates = [
                [r.get("time"), r.get("open"), r.get("high"), r.get("low"), r.get("close"), r.get("tick_volume")]
                for r in rates
            ]
            rates_cache[cache_key] = compact_rates
            return compact_rates
        except Exception as e:
            logger.error(f"Failed to fetch rates: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to fetch rates from terminal: {e!s}")


@app.get("/api/v1/market/rates/range", dependencies=[Depends(verify_api_key)])
@app.get("/api/v1/chart/rates/range", dependencies=[Depends(verify_api_key)], include_in_schema=False)
def get_chart_rates_range(
    symbol: str = Query(..., description="Financial asset symbol e.g., EURUSD"),
    timeframe: str = Query("H1", description="Timeframe e.g. M1, M5, H1, D1"),
    date_from: str = Query(..., description="Start date/time in ISO format or YYYY-MM-DD HH:MM:SS"),
    date_to: str = Query(..., description="End date/time in ISO format or YYYY-MM-DD HH:MM:SS"),
):
    tf_val = TIMEFRAME_MAP.get(timeframe.upper())
    if not tf_val:
        raise HTTPException(status_code=400, detail=f"Invalid timeframe '{timeframe}'")

    cache_key = (symbol, tf_val, date_from, date_to)
    if cache_key in rates_cache:
        return rates_cache[cache_key]

    try:
        rates = grpc_client.get_rates_range(symbol, tf_val, date_from, date_to)
        compact_rates = [
            [r.get("time"), r.get("open"), r.get("high"), r.get("low"), r.get("close"), r.get("tick_volume")]
            for r in rates
        ]
        rates_cache[cache_key] = compact_rates
        return compact_rates
    except Exception as e:
        logger.error(f"Failed to fetch rates range: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch rates range from terminal: {e!s}")


@app.get("/api/v1/market/rates/from", dependencies=[Depends(verify_api_key)])
@app.get("/api/v1/chart/rates/from", dependencies=[Depends(verify_api_key)], include_in_schema=False)
def get_chart_rates_from(
    symbol: str = Query(..., description="Financial asset symbol e.g., EURUSD"),
    timeframe: str = Query("H1", description="Timeframe e.g. M1, M5, H1, D1"),
    date_from: str = Query(..., description="Start date/time in ISO format or YYYY-MM-DD HH:MM:SS"),
    count: int = Query(500, ge=1, le=10000, description="Number of candles to retrieve"),
):
    tf_val = TIMEFRAME_MAP.get(timeframe.upper())
    if not tf_val:
        raise HTTPException(status_code=400, detail=f"Invalid timeframe '{timeframe}'")

    cache_key = (symbol, tf_val, date_from, count)
    if cache_key in rates_cache:
        return rates_cache[cache_key]

    try:
        rates = grpc_client.get_rates_from(symbol, tf_val, date_from, count)
        compact_rates = [
            [r.get("time"), r.get("open"), r.get("high"), r.get("low"), r.get("close"), r.get("tick_volume")]
            for r in rates
        ]
        rates_cache[cache_key] = compact_rates
        return compact_rates
    except Exception as e:
        logger.error(f"Failed to fetch rates from: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch rates from terminal: {e!s}")


# ---------------------------------------------------------
# Dynamic Symbol Provisioning
# ---------------------------------------------------------
@app.get("/api/v1/symbols/broker", dependencies=[Depends(verify_api_key)])
def list_broker_symbols(group: str = Query("", description="Filter group pattern, e.g., *forex*")):
    try:
        symbols = grpc_client.get_symbols(group)
        return {"symbols": symbols}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get symbols list: {e!s}")


@app.get("/api/v1/symbols/active", dependencies=[Depends(verify_api_key)])
def list_active_symbols():
    try:
        symbols = grpc_client.get_symbols()
        active = [s for s in symbols if s.get("visible", False)]
        return {"active_symbols": active}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get active symbols: {e!s}")


@app.post("/api/v1/symbols/active", response_model=SymbolProvisionResponse, dependencies=[Depends(verify_api_key)])
async def add_active_symbol(
    payload: SymbolProvisionRequest,
    background_tasks: BackgroundTasks,
):
    symbol = payload.symbol.upper()
    try:
        success = grpc_client.select_symbol(symbol, enable=True)
        if not success:
            raise HTTPException(status_code=400, detail=f"Failed to enable symbol {symbol} in terminal.")

        backfill_status = "not_requested"
        if payload.auto_backfill and backfill_worker:
            backfill_status = "queued"
            resolved_date_from = None
            resolved_date_to = None
            if payload.days and payload.days > 0:
                now = datetime.now(timezone.utc)
                resolved_date_to = now.strftime("%Y-%m-%dT%H:%M:%SZ")
                resolved_date_from = (now - timedelta(days=payload.days)).strftime("%Y-%m-%dT%H:%M:%SZ")

            background_tasks.add_task(
                backfill_worker.run_initial_backfill,
                symbol=symbol,
                timeframes=payload.timeframes,
                candle_count=payload.candle_count,
                date_from=resolved_date_from,
                date_to=resolved_date_to,
            )

        # Start live background polling task if not active
        if symbol not in active_poll_tasks:
            task = asyncio.create_task(poll_ticks_loop(symbol))
            active_poll_tasks[symbol] = task

        return SymbolProvisionResponse(
            symbol=symbol,
            success=True,
            message=f"Symbol {symbol} provisioned and activated.",
            backfill_status=backfill_status,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error provisioning symbol: {e!s}")


@app.delete(
    "/api/v1/symbols/active/{symbol}", response_model=SymbolProvisionResponse, dependencies=[Depends(verify_api_key)]
)
def remove_active_symbol(symbol: str):
    symbol = symbol.upper()
    try:
        success = grpc_client.select_symbol(symbol, enable=False)
        if success:
            if symbol in active_poll_tasks:
                task = active_poll_tasks.pop(symbol)
                task.cancel()
                logger.info(f"Terminated background tick task for deactivated symbol {symbol}")
            return SymbolProvisionResponse(
                symbol=symbol,
                success=True,
                message=f"Symbol {symbol} de-provisioned and removed.",
            )
        else:
            raise HTTPException(status_code=400, detail=f"Failed to disable symbol {symbol} in terminal.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error removing symbol: {e!s}")


# ---------------------------------------------------------
# Real-Time WebSocket Streaming (Candle 0 & Live Ticks)
# ---------------------------------------------------------

@app.websocket("/api/v1/market/ws/{symbol}")
@app.websocket("/api/v1/chart/ws/{symbol}")
async def websocket_endpoint(websocket: WebSocket, symbol: str):
    symbol = symbol.upper()
    await websocket.accept()
    logger.info(f"WebSocket client connected for symbol: {symbol}")

    if symbol not in symbol_subscriptions:
        symbol_subscriptions[symbol] = set()
    symbol_subscriptions[symbol].add(websocket)
    WS_CONNECTIONS_GAUGE.labels(symbol=symbol).set(len(symbol_subscriptions[symbol]))

    # Deliver immediate in-memory snapshot of Candle 0 states upon connection
    if candle_manager:
        initial_states = {}
        for tf in candle_manager.supported_timeframes:
            st = candle_manager.get_candle0(symbol, tf)
            if st:
                initial_states[tf] = st.to_compact_array()
        if initial_states:
            try:
                await websocket.send_json(
                    {
                        "type": "snapshot",
                        "symbol": symbol,
                        "candle0": initial_states,
                    }
                )
            except Exception as e:
                logger.warning(f"Failed to send initial snapshot to WebSocket client for {symbol}: {e}")

    if symbol not in active_poll_tasks:
        task = asyncio.create_task(poll_ticks_loop(symbol))
        active_poll_tasks[symbol] = task

    try:
        while True:
            # Keep connection alive & handle incoming pings
            data = await websocket.receive_text()
            logger.debug(f"Received client message on {symbol}: {data}")

    except (WebSocketDisconnect, Exception):
        logger.info(f"WebSocket client disconnected for symbol: {symbol}")
    finally:
        if symbol in symbol_subscriptions:
            symbol_subscriptions[symbol].discard(websocket)
            WS_CONNECTIONS_GAUGE.labels(symbol=symbol).set(len(symbol_subscriptions[symbol]))
            if not symbol_subscriptions[symbol]:
                symbol_subscriptions.pop(symbol, None)
                task = active_poll_tasks.pop(symbol, None)
                if task:
                    task.cancel()
                    logger.info(f"Stopped background tick polling for {symbol} (0 active subscribers).")
