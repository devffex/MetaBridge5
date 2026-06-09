import os
import asyncio
import logging
from typing import Dict, List, Set, Optional
from fastapi import FastAPI, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from cachetools import TTLCache

from app.grpc_client import TerminalGRPCClient

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("chart_gateway")

app = FastAPI(
    title="Savisor Chart Gateway",
    description="High-performance pass-through gateway for TradingView charting with dynamic asset provisioning",
    version="1.0.0"
)

# Enable CORS for frontend integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global gRPC client
grpc_client: Optional[TerminalGRPCClient] = None

# In-memory caches
# Rates cache stores historical data arrays with 5-second TTL to de-duplicate UI spam
rates_cache = TTLCache(maxsize=1000, ttl=5)
# Active background tick polling tasks
active_poll_tasks: Dict[str, asyncio.Task] = {}
# WebSocket connections grouped by symbol
symbol_subscriptions: Dict[str, Set[WebSocket]] = {}
# Thread safe lock for WS broadcasts
ws_lock = asyncio.Lock()

# MT5 Timeframe Constants Mapper
TIMEFRAME_MAP = {
    "M1": 1,
    "M2": 2,
    "M3": 3,
    "M4": 4,
    "M5": 5,
    "M6": 6,
    "M10": 10,
    "M12": 12,
    "M15": 15,
    "M20": 20,
    "M30": 30,
    "H1": 16385,
    "H2": 16386,
    "H3": 16387,
    "H4": 16388,
    "H6": 16390,
    "H8": 16392,
    "H12": 16396,
    "D1": 16408,
    "W1": 32769,
    "MN1": 49153
}

# ---------------------------------------------------------
# Security Dependency
# ---------------------------------------------------------
def verify_api_key(x_api_key: Optional[str] = Header(None)):
    expected_key = os.environ.get("SAVISOR_API_KEY")
    if expected_key and x_api_key != expected_key:
        raise HTTPException(status_code=401, detail="Invalid or missing X-API-Key header")
    return x_api_key

# ---------------------------------------------------------
# Pydantic Schemas
# ---------------------------------------------------------
class SymbolProvisionRequest(BaseModel):
    symbol: str

class SymbolProvisionResponse(BaseModel):
    symbol: str
    success: bool
    message: str

# ---------------------------------------------------------
# Lifecycle Events
# ---------------------------------------------------------
@app.on_event("startup")
async def startup_event():
    global grpc_client
    grpc_client = TerminalGRPCClient()
    logger.info("Chart Gateway API started.")

@app.on_event("shutdown")
async def shutdown_event():
    global grpc_client
    # Cancel all active polling tasks
    for symbol, task in active_poll_tasks.items():
        logger.info(f"Cancelling poll task for {symbol}...")
        task.cancel()
    if grpc_client:
        grpc_client.close()
    logger.info("Chart Gateway API stopped.")

# ---------------------------------------------------------
# API Endpoints
# ---------------------------------------------------------
@app.get("/health")
def health_check():
    if not grpc_client:
        return {"status": "error", "message": "Client not initialized"}
    daemon_health = grpc_client.get_health()
    return {
        "status": "ok" if daemon_health.get("status") == "ok" else "degraded",
        "gateway": "savisor-chart-gateway",
        "daemon": daemon_health
    }

# --- Historical Rates (Candles) ---
@app.get("/api/v1/chart/rates", dependencies=[Depends(verify_api_key)])
def get_chart_rates(
    symbol: str = Query(..., description="Financial asset symbol e.g., EURUSD"),
    timeframe: str = Query("H1", description="Timeframe e.g. M1, M5, H1, D1"),
    count: int = Query(500, ge=1, le=10000, description="Number of candles to retrieve"),
    start_pos: int = Query(0, ge=0, description="Starting bar index (0 represents the latest bar)")
):
    tf_val = TIMEFRAME_MAP.get(timeframe.upper())
    if not tf_val:
        raise HTTPException(
            status_code=400, 
            detail=f"Invalid timeframe '{timeframe}'. Supported: {list(TIMEFRAME_MAP.keys())}"
        )
    
    # Check RAM Cache first
    cache_key = (symbol, tf_val, start_pos, count)
    if cache_key in rates_cache:
        logger.debug(f"Cache hit for rates: {cache_key}")
        return rates_cache[cache_key]

    try:
        # Fetch from MT5 binary history cache via gRPC (Cache #1)
        rates = grpc_client.get_rates_from_pos(symbol, tf_val, start_pos, count)
        
        # Convert to Compact JSON (Array of Arrays)
        # Format: [[time, open, high, low, close, volume], ...]
        compact_rates = [
            [
                r.get("time"),
                r.get("open"),
                r.get("high"),
                r.get("low"),
                r.get("close"),
                r.get("tick_volume")
            ]
            for r in rates
        ]
        
        # Store in RAM Cache (Cache #2)
        rates_cache[cache_key] = compact_rates
        return compact_rates
    except Exception as e:
        logger.error(f"Failed to fetch rates: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch rates from terminal: {str(e)}")

# --- Symbol Management (Dynamic Provisioning) ---
@app.get("/api/v1/symbols/broker", dependencies=[Depends(verify_api_key)])
def list_broker_symbols(group: str = Query("", description="Filter group pattern, e.g., *forex*")):
    try:
        symbols = grpc_client.get_symbols(group)
        return {"symbols": symbols}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get symbols list: {str(e)}")

@app.get("/api/v1/symbols/active", dependencies=[Depends(verify_api_key)])
def list_active_symbols():
    try:
        # Fetch active symbols from Market Watch
        symbols = grpc_client.get_symbols()
        # Filter for visible ones
        active = [s for s in symbols if s.get("visible", False)]
        return {"active_symbols": active}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get active symbols: {str(e)}")

@app.post("/api/v1/symbols/active", response_model=SymbolProvisionResponse, dependencies=[Depends(verify_api_key)])
def add_active_symbol(payload: SymbolProvisionRequest):
    symbol = payload.symbol.upper()
    try:
        # Enable in MT5 Market Watch (starts history cache sync and broker tick stream)
        success = grpc_client.select_symbol(symbol, enable=True)
        if success:
            return SymbolProvisionResponse(
                symbol=symbol,
                success=True,
                message=f"Symbol {symbol} provisioned and activated in Market Watch."
            )
        else:
            raise HTTPException(status_code=400, detail=f"Failed to enable symbol {symbol} in terminal.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error provisioning symbol: {str(e)}")

@app.delete("/api/v1/symbols/active/{symbol}", response_model=SymbolProvisionResponse, dependencies=[Depends(verify_api_key)])
def remove_active_symbol(symbol: str):
    symbol = symbol.upper()
    try:
        # Disable in MT5 Market Watch to stop wasting CPU/bandwidth
        success = grpc_client.select_symbol(symbol, enable=False)
        if success:
            # Terminate polling loop if active
            if symbol in active_poll_tasks:
                task = active_poll_tasks.pop(symbol)
                task.cancel()
                logger.info(f"Terminated background tick task for deactivated symbol {symbol}")
            return SymbolProvisionResponse(
                symbol=symbol,
                success=True,
                message=f"Symbol {symbol} de-provisioned and removed from Market Watch."
            )
        else:
            raise HTTPException(status_code=400, detail=f"Failed to disable symbol {symbol} in terminal.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error removing symbol: {str(e)}")

# ---------------------------------------------------------
# WebSockets Real-Time Tick Streaming
# ---------------------------------------------------------
async def poll_ticks_loop(symbol: str):
    """Background task to poll ticks for a symbol and broadcast to subscribers."""
    logger.info(f"Starting background tick poll loop for {symbol}...")
    last_tick_time = 0
    last_tick_bid = 0.0
    
    try:
        while True:
            try:
                tick = grpc_client.get_symbol_info_tick(symbol)
                if tick:
                    tick_time = tick.get("time", 0)
                    bid = tick.get("bid", 0.0)
                    
                    # Broadcast only if the tick is new
                    if tick_time != last_tick_time or bid != last_tick_bid:
                        last_tick_time = tick_time
                        last_tick_bid = bid
                        
                        # Gather active websockets
                        websockets = symbol_subscriptions.get(symbol, set())
                        if websockets:
                            # Compact Tick Format: [time, bid, ask, last, volume]
                            payload = [
                                tick_time,
                                bid,
                                tick.get("ask", 0.0),
                                tick.get("last", 0.0),
                                tick.get("volume", 0)
                            ]
                            async with ws_lock:
                                # Send to all active subscribers
                                dead_ws = set()
                                for ws in websockets:
                                    try:
                                        await ws.send_json(payload)
                                    except Exception:
                                        dead_ws.add(ws)
                                # Clean up dead connections
                                if dead_ws:
                                    websockets.difference_update(dead_ws)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in tick polling loop for {symbol}: {e}")
            
            # Poll every 250ms for low latency tick tracking
            await asyncio.sleep(0.25)
            
    finally:
        logger.info(f"Stopped background tick poll loop for {symbol}.")

@app.websocket("/api/v1/chart/ws/{symbol}")
async def websocket_endpoint(websocket: WebSocket, symbol: str):
    symbol = symbol.upper()
    await websocket.accept()
    logger.info(f"WebSocket client connected for symbol: {symbol}")
    
    # Register subscription
    if symbol not in symbol_subscriptions:
        symbol_subscriptions[symbol] = set()
    symbol_subscriptions[symbol].add(websocket)
    
    # Start polling loop task for this symbol if not already running
    if symbol not in active_poll_tasks:
        task = asyncio.create_task(poll_ticks_loop(symbol))
        active_poll_tasks[symbol] = task
        
    try:
        while True:
            # Keep connection alive & listen for client messages if any
            data = await websocket.receive_text()
            logger.debug(f"Received WebSocket message: {data}")
            
    except WebSocketDisconnect:
        logger.info(f"WebSocket client disconnected for symbol: {symbol}")
    finally:
        # Clean up client registration
        if symbol in symbol_subscriptions:
            symbol_subscriptions[symbol].discard(websocket)
            # If no more active connections, stop the polling loop to save resources
            if not symbol_subscriptions[symbol]:
                symbol_subscriptions.pop(symbol)
                task = active_poll_tasks.pop(symbol, None)
                if task:
                    task.cancel()
                    logger.info(f"Stopped background tick polling for {symbol} as there are no active WS connections.")
