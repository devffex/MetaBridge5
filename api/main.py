import logging
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI

# Import mt5 safely using the same import logic as our router
from routers.trading import mt5
from routers.trading import router as trading_router

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("api")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager to handle MT5 initialization and shutdown."""
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

# Register the trading router
app.include_router(trading_router)


@app.get("/")
def read_root() -> dict[str, Any]:
    """Root endpoint returning basic API metadata."""
    logger.info("Root endpoint accessed")
    return {
        "title": app.title,
        "description": app.description,
        "version": app.version,
        "status": "online",
    }


@app.get("/health")
def health_check() -> dict[str, str]:
    """Simple health check endpoint."""
    logger.info("Health check endpoint accessed")
    return {"status": "ok"}
