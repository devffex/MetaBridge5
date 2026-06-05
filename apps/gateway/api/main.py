import logging
import shutil
from contextlib import asynccontextmanager
from typing import Any

from fastapi import Depends, FastAPI
from fastapi.responses import JSONResponse

from auth import enforce_api_key_configured, require_api_key

# Import mt5 safely using the same import logic as our router
from routers.trading import mt5
from routers.trading import router as trading_router

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("api")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager to handle MT5 initialization and shutdown."""
    # Fail fast if the API key is not configured
    enforce_api_key_configured()

    yield

    logger.info("Shutting down MetaTrader 5 connection...")
    try:
        mt5.shutdown()
        logger.info("MetaTrader 5 connection shut down successfully.")
    except Exception as e:
        logger.error(f"Exception during MT5 shutdown: {e}")


app = FastAPI(
    title="Savisor Node API",
    description="REST API wrapper for exposing MetaTrader 5 terminal running in Wine.",
    version="0.1.0",
    lifespan=lifespan,
)

# Register the trading router with API key auth applied to all its endpoints
app.include_router(trading_router, dependencies=[Depends(require_api_key)])


@app.get("/")
def read_root() -> dict[str, Any]:
    """Root endpoint returning basic API metadata.

    Unauthenticated — exposes no sensitive data.
    """
    logger.info("Root endpoint accessed")
    return {
        "title": app.title,
        "description": app.description,
        "version": app.version,
        "status": "online",
    }


@app.get("/health")
def health_check() -> Any:
    """Health check endpoint exposing native disk space and MT5 connection status.

    Unauthenticated — used by container orchestrators and metrics collection.
    """
    logger.info("Health check endpoint accessed")

    # 1. Get disk space metrics using standard shutil (works on Linux/Windows/Wine)
    try:
        total, used, free = shutil.disk_usage("/")
        disk_stats = {"total": total, "used": used, "free": free}
    except Exception as e:
        logger.error(f"Failed to read disk space: {e}")
        disk_stats = {"total": 0, "used": 0, "free": 0}

    # 2. Get MT5 connection state
    mt5_connected = False
    mt5_login = 0
    try:
        info = mt5.terminal_info()
        if info is not None:
            mt5_connected = getattr(info, "connected", False)
        acct = mt5.account_info()
        if acct is not None:
            mt5_login = getattr(acct, "login", 0)
    except Exception as e:
        logger.warning(f"Error checking MT5 terminal info during health check: {e}")

    content = {
        "status": "ok" if mt5_connected else "degraded",
        "mt5_connected": mt5_connected,
        "mt5_login": mt5_login,
        "disk": disk_stats,
    }

    if not mt5_connected:
        return JSONResponse(status_code=503, content=content)

    return content
