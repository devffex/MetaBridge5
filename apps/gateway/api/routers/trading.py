import asyncio
import logging
import os
from datetime import datetime
from typing import Any

from fastapi import APIRouter, HTTPException, Query

# Schemas absolute imports
from schemas.base import datetime_to_timestamp
from schemas.history import (
    HistoryDealsRequest,
    HistoryDealsResponse,
    HistoryDealsTotalRequest,
    HistoryDealsTotalResponse,
    HistoryOrdersRequest,
    HistoryOrdersResponse,
    HistoryOrdersTotalRequest,
    HistoryOrdersTotalResponse,
)
from schemas.market_data import (
    CopyRatesFromPosRequest,
    CopyRatesFromRequest,
    CopyRatesRangeRequest,
    CopyRatesResponse,
    CopyTicksFromRequest,
    CopyTicksRangeRequest,
    CopyTicksResponse,
    MarketBookActionResponse,
    MarketBookGetResponse,
    MarketBookRequest,
    OrdersGetResponse,
    OrdersTotalResponse,
    TickResponse,
)
from schemas.orders import (
    OrderCalcMarginRequest,
    OrderCalcMarginResponse,
    OrderCalcProfitRequest,
    OrderCalcProfitResponse,
    OrderCheckResult,
    OrderSendResult,
    TradeRequest,
)
from schemas.positions import PositionsResponse, PositionsTotalResponse
from schemas.symbols import (
    SymbolInfoRequest,
    SymbolInfoResponse,
    SymbolInfoTickRequest,
    SymbolSelectRequest,
    SymbolSelectResponse,
    SymbolsGetResponse,
    SymbolsTotalResponse,
)
from schemas.terminal import (
    AccountInfoResponse,
    AuthenticationRequest,
    LastErrorResponse,
    TerminalInfoResponse,
    VersionResponse,
)

logger = logging.getLogger("api.trading")

# ---------------------------------------------------------
# MetaTrader5 Fallback Import / Mocking
# ---------------------------------------------------------
try:
    if os.environ.get("METAFORGE_MOCK_MT5") == "1":
        raise ImportError("Mocking requested via environment variable")
    import MetaTrader5 as mt5  # noqa: N813
except ImportError:
    logger.warning(
        "MetaTrader5 library not found or mocking requested. Using MockMT5 fallback."
    )
    from tests.mock_mt5 import MockMT5

    mt5 = MockMT5()

# ---------------------------------------------------------
# Operations Config & Helper Functions
# ---------------------------------------------------------
NULLABLE_OPS = frozenset(
    {
        "positions_get",
        "history_deals_get",
        "history_orders_get",
        "market_book_get",
        "symbol_info",
        "symbol_info_tick",
        "symbols_get",
        "copy_ticks_range",
        "copy_ticks_from",
        "copy_rates_range",
        "copy_rates_from",
        "copy_rates_from_pos",
        "order_calc_profit",
        "order_calc_margin",
        "orders_get",
    }
)


def _serialize_mt5(obj):
    if hasattr(obj, "_asdict"):
        d = obj._asdict()
        return {k: _serialize_mt5(v) for k, v in d.items()}
    elif isinstance(obj, (list, tuple)):
        return [_serialize_mt5(i) for i in obj]
    elif isinstance(obj, dict):
        return {k: _serialize_mt5(v) for k, v in obj.items()}
    return obj


async def run_mt5_op(
    op: str, params: dict[str, Any], as_dataframe: bool = False
) -> Any:
    """Executes a MetaTrader5 operation in a separate thread
    and converts the response.
    """
    # Dynamic on-demand initialization check
    try:
        if op != "initialize":
            info = mt5.terminal_info()
            if info is None:
                logger.info("MT5 connection not initialized. Initializing on-demand...")
                # Connect in a separate thread to avoid blocking the main event loop
                init_ok = await asyncio.to_thread(mt5.initialize)
                if not init_ok:
                    err = mt5.last_error()
                    logger.warning(f"On-demand MT5 initialization failed: {err}")
    except Exception as e:
        logger.warning(f"Exception during dynamic MT5 initialization: {e}")

    # Enforce active manual authentication for operational commands
    if op not in ("initialize", "terminal_info", "version", "last_error", "login"):
        info = mt5.terminal_info()
        acct = mt5.account_info()
        if (
            info is None
            or not getattr(info, "connected", False)
            or acct is None
            or getattr(acct, "login", 0) == 0
        ):
            raise HTTPException(
                status_code=412,
                detail=(
                    "Terminal not authenticated. "
                    "Please log in manually to your broker account via VNC first."
                ),
            )

    op_func = getattr(mt5, op, None)
    if op_func is None:
        raise HTTPException(
            status_code=400, detail=f"Operation '{op}' not supported by MT5 API."
        )

    def _execute():
        if op == "login":
            return op_func(
                params["login"],
                password=params.get("password"),
                server=params.get("server"),
            )
        elif op == "order_calc_margin":
            return op_func(
                params["action"],
                params["symbol"],
                params["volume"],
                params["price"],
            )
        elif op == "order_calc_profit":
            return op_func(
                params["action"],
                params["symbol"],
                params["volume"],
                params["price_open"],
                params["price_close"],
            )
        elif op in ("history_orders_total", "history_deals_total"):
            return op_func(params["date_from"], params["date_to"])
        elif op in ("order_send", "order_check"):
            return op_func(params)
        elif op == "copy_ticks_from":
            return op_func(
                params["symbol"],
                params["date_from"],
                params["count"],
                params["flags"],
            )
        elif op == "copy_ticks_range":
            return op_func(
                params["symbol"],
                params["date_from"],
                params["date_to"],
                params["flags"],
            )
        elif op == "copy_rates_from":
            return op_func(
                params["symbol"],
                params["timeframe"],
                params["date_from"],
                params["count"],
            )
        elif op == "copy_rates_range":
            return op_func(
                params["symbol"],
                params["timeframe"],
                params["date_from"],
                params["date_to"],
            )
        elif op == "copy_rates_from_pos":
            return op_func(
                params["symbol"],
                params["timeframe"],
                params["start_pos"],
                params["count"],
            )
        elif op in (
            "market_book_add",
            "market_book_release",
            "market_book_get",
            "symbol_info",
            "symbol_info_tick",
        ):
            return op_func(params["symbol"])
        elif op == "symbol_select":
            if "enable" in params:
                return op_func(params["symbol"], params["enable"])
            return op_func(params["symbol"])
        else:
            return op_func(**params)

    try:
        # Offload the blocking Windows socket/named-pipe calls
        # to keep the event loop responsive
        result = await asyncio.to_thread(_execute)

        if result is None:
            if op in NULLABLE_OPS:
                return None
            else:
                err = mt5.last_error()
                raise HTTPException(
                    status_code=400, detail=f"MT5 Error {err[0]}: {err[1]}"
                )

        # Pandas / NumPy conversions
        try:
            import numpy as np
            import pandas as pd

            if isinstance(result, np.ndarray):
                df = pd.DataFrame(result)
                df = df.replace({np.nan: None})
                result = df.to_dict(orient="records")
            elif isinstance(result, (list, tuple)):
                if len(result) > 0 and hasattr(result[0], "_asdict"):
                    df = pd.DataFrame([r._asdict() for r in result])
                    df = df.replace({np.nan: None})
                    result = df.to_dict(orient="records")
        except ImportError:
            pass

        if as_dataframe:
            import pandas as pd

            return pd.DataFrame(result)

        return _serialize_mt5(result)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in MT5 operation '{op}': {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"In-process bridge error: {e}"
        ) from e


# Router Setup
router = APIRouter(prefix="/api/v1/terminals", tags=["trading"])

# ---------------------------------------------------------
# Endpoint Implementations
# ---------------------------------------------------------


@router.post("/trade/order", response_model=OrderSendResult)
async def send_order(
    payload: TradeRequest,
):
    """Send a trade order."""
    params = payload.model_dump(exclude_none=True)
    if "expiration" in params and isinstance(params["expiration"], datetime):
        params["expiration"] = datetime_to_timestamp(params["expiration"])

    result = await run_mt5_op("order_send", params)
    if result is None:
        raise HTTPException(status_code=400, detail="Order send failed.")
    return OrderSendResult(**result)


@router.post(
    "/trade/order/check",
    response_model=OrderCheckResult,
)
async def check_order(
    payload: TradeRequest,
):
    """Check margin sufficiency for a trade order."""
    params = payload.model_dump(exclude_none=True)
    if "expiration" in params and isinstance(params["expiration"], datetime):
        params["expiration"] = datetime_to_timestamp(params["expiration"])

    result = await run_mt5_op("order_check", params)
    if result is None:
        raise HTTPException(status_code=400, detail="Order check failed.")
    return OrderCheckResult(**result)


@router.post(
    "/trade/order/calc/profit",
    response_model=OrderCalcProfitResponse,
)
async def calc_order_profit(
    payload: OrderCalcProfitRequest,
):
    """Estimate profit for a trading operation."""
    params = payload.model_dump()
    result = await run_mt5_op("order_calc_profit", params)
    if result is None:
        raise HTTPException(status_code=400, detail="Profit calculation failed.")
    return OrderCalcProfitResponse(profit=result)


@router.post(
    "/trade/order/calc/margin",
    response_model=OrderCalcMarginResponse,
)
async def calc_order_margin(
    payload: OrderCalcMarginRequest,
):
    """Estimate margin for a trading operation."""
    params = payload.model_dump()
    result = await run_mt5_op("order_calc_margin", params)
    if result is None:
        raise HTTPException(status_code=400, detail="Margin calculation failed.")
    return OrderCalcMarginResponse(margin=result)


@router.get(
    "/trade/positions",
    response_model=PositionsResponse,
)
async def get_positions(
    symbol: str | None = Query(None, description="Filter positions by symbol"),
    group: str | None = Query(None, description="Filter positions by group"),
    ticket: int | None = Query(None, description="Filter positions by ticket"),
):
    """Get active positions."""
    provided_filters = sum(x is not None for x in [symbol, group, ticket])
    if provided_filters > 1:
        raise HTTPException(
            status_code=422,
            detail="Parameters symbol, group, and ticket are mutually exclusive.",
        )

    params = {}
    if symbol is not None:
        params["symbol"] = symbol
    elif group is not None:
        params["group"] = group
    elif ticket is not None:
        params["ticket"] = ticket

    result = await run_mt5_op("positions_get", params)
    if result is None:
        return PositionsResponse(positions=[])
    return PositionsResponse(positions=result)


@router.get(
    "/trade/positions/total",
    response_model=PositionsTotalResponse,
)
async def get_positions_total():
    """Get the number of active positions."""
    result = await run_mt5_op("positions_total", {})
    if result is None:
        return PositionsTotalResponse(total=0)
    return PositionsTotalResponse(total=result)


@router.get(
    "/trade/terminal/info",
    response_model=TerminalInfoResponse,
)
async def get_terminal_info():
    """Get the connected MetaTrader 5 client terminal status and settings."""
    result = await run_mt5_op("terminal_info", {})
    return TerminalInfoResponse(**result)


@router.get(
    "/trade/account",
    response_model=AccountInfoResponse,
)
async def get_account_info():
    """Get info on the current trading account."""
    result = await run_mt5_op("account_info", {})
    return AccountInfoResponse(**result)


@router.get("/trade/version", response_model=VersionResponse)
async def get_version():
    """Return the MetaTrader 5 terminal version."""
    result = await run_mt5_op("version", {})
    return VersionResponse(version=result[0], build=result[1], release_date=result[2])


@router.get(
    "/trade/last-error",
    response_model=LastErrorResponse,
)
async def get_last_error():
    """Return data on the last error."""
    result = await run_mt5_op("last_error", {})
    return LastErrorResponse(code=result[0], description=result[1])


@router.post(
    "/trade/history/deals",
    response_model=HistoryDealsResponse,
)
async def get_history_deals(
    payload: HistoryDealsRequest,
):
    """Get deals from trading history."""
    params = {}
    if payload.date_from is not None and payload.date_to is not None:
        params["date_from"] = datetime_to_timestamp(payload.date_from)
        params["date_to"] = datetime_to_timestamp(payload.date_to)
        if payload.group is not None:
            params["group"] = payload.group
    elif payload.ticket is not None:
        params["ticket"] = payload.ticket
    elif payload.position is not None:
        params["position"] = payload.position

    result = await run_mt5_op("history_deals_get", params)
    if result is None:
        return HistoryDealsResponse(deals=[])
    return HistoryDealsResponse(deals=result)


@router.post(
    "/trade/history/deals/total",
    response_model=HistoryDealsTotalResponse,
)
async def get_history_deals_total(
    payload: HistoryDealsTotalRequest,
):
    """Get the number of deals from trading history."""
    params = {
        "date_from": datetime_to_timestamp(payload.date_from),
        "date_to": datetime_to_timestamp(payload.date_to),
    }
    result = await run_mt5_op("history_deals_total", params)
    if result is None:
        return HistoryDealsTotalResponse(total=0)
    return HistoryDealsTotalResponse(total=result)


@router.post(
    "/trade/history/orders",
    response_model=HistoryOrdersResponse,
)
async def get_history_orders(
    payload: HistoryOrdersRequest,
):
    """Get orders from trading history."""
    params = {}
    if payload.date_from is not None and payload.date_to is not None:
        params["date_from"] = datetime_to_timestamp(payload.date_from)
        params["date_to"] = datetime_to_timestamp(payload.date_to)
        if payload.group is not None:
            params["group"] = payload.group
    elif payload.ticket is not None:
        params["ticket"] = payload.ticket
    elif payload.position is not None:
        params["position"] = payload.position

    result = await run_mt5_op("history_orders_get", params)
    if result is None:
        return HistoryOrdersResponse(orders=[])
    return HistoryOrdersResponse(orders=result)


@router.post(
    "/trade/history/orders/total",
    response_model=HistoryOrdersTotalResponse,
)
async def get_history_orders_total(
    payload: HistoryOrdersTotalRequest,
):
    """Get the number of orders from trading history."""
    params = {
        "date_from": datetime_to_timestamp(payload.date_from),
        "date_to": datetime_to_timestamp(payload.date_to),
    }
    result = await run_mt5_op("history_orders_total", params)
    if result is None:
        return HistoryOrdersTotalResponse(total=0)
    return HistoryOrdersTotalResponse(total=result)


@router.get(
    "/trade/orders/total",
    response_model=OrdersTotalResponse,
)
async def get_orders_total():
    """Get the number of active orders."""
    result = await run_mt5_op("orders_total", {})
    if result is None:
        return OrdersTotalResponse(total=0)
    return OrdersTotalResponse(total=result)


@router.get("/trade/orders", response_model=OrdersGetResponse)
async def get_orders(
    symbol: str | None = Query(None, description="Filter orders by symbol"),
    group: str | None = Query(None, description="Filter orders by group"),
    ticket: int | None = Query(None, description="Filter orders by ticket"),
):
    """Get active orders with the ability to filter by symbol or ticket."""
    provided_filters = sum(x is not None for x in [symbol, group, ticket])
    if provided_filters > 1:
        raise HTTPException(
            status_code=422,
            detail="Parameters symbol, group, and ticket are mutually exclusive.",
        )

    params = {}
    if symbol is not None:
        params["symbol"] = symbol
    elif group is not None:
        params["group"] = group
    elif ticket is not None:
        params["ticket"] = ticket

    result = await run_mt5_op("orders_get", params)
    if result is None:
        return {"orders": []}
    return {"orders": result}


@router.post(
    "/trade/market/ticks/range",
    response_model=CopyTicksResponse,
)
async def copy_ticks_range(
    payload: CopyTicksRangeRequest,
):
    """Get ticks for the specified date range."""
    params = {
        "symbol": payload.symbol,
        "date_from": datetime_to_timestamp(payload.date_from),
        "date_to": datetime_to_timestamp(payload.date_to),
        "flags": payload.flags.value,
    }
    result = await run_mt5_op("copy_ticks_range", params)
    if result is None:
        return CopyTicksResponse(ticks=[])
    # Enforce upper limit cap of 10,000 items to prevent memory exhaustion
    if len(result) > 10000:
        result = result[:10000]
    return CopyTicksResponse(ticks=result)


@router.post(
    "/trade/market/ticks/from",
    response_model=CopyTicksResponse,
)
async def copy_ticks_from(
    payload: CopyTicksFromRequest,
):
    """Get ticks starting from the specified date."""
    # Enforce maximum count limit of 10,000
    capped_count = min(payload.count, 10000)
    params = {
        "symbol": payload.symbol,
        "date_from": datetime_to_timestamp(payload.date_from),
        "count": capped_count,
        "flags": payload.flags.value,
    }
    result = await run_mt5_op("copy_ticks_from", params)
    if result is None:
        return CopyTicksResponse(ticks=[])
    return CopyTicksResponse(ticks=result)


@router.post(
    "/trade/market/rates/range",
    response_model=CopyRatesResponse,
)
async def copy_rates_range(
    payload: CopyRatesRangeRequest,
):
    """Get bars in the specified date range."""
    params = {
        "symbol": payload.symbol,
        "timeframe": payload.timeframe.value,
        "date_from": datetime_to_timestamp(payload.date_from),
        "date_to": datetime_to_timestamp(payload.date_to),
    }
    result = await run_mt5_op("copy_rates_range", params)
    if result is None:
        return CopyRatesResponse(rates=[])
    # Enforce upper limit cap of 5,000 items to prevent memory exhaustion
    if len(result) > 5000:
        result = result[:5000]
    return CopyRatesResponse(rates=result)


@router.post(
    "/trade/market/rates/from-pos",
    response_model=CopyRatesResponse,
)
async def copy_rates_from_pos(
    payload: CopyRatesFromPosRequest,
):
    """Get bars from the specified index position."""
    # Enforce maximum count limit of 5,000
    capped_count = min(payload.count, 5000)
    params = {
        "symbol": payload.symbol,
        "timeframe": payload.timeframe.value,
        "start_pos": payload.start_pos,
        "count": capped_count,
    }
    result = await run_mt5_op("copy_rates_from_pos", params)
    if result is None:
        return CopyRatesResponse(rates=[])
    return CopyRatesResponse(rates=result)


@router.post(
    "/trade/market/rates/from",
    response_model=CopyRatesResponse,
)
async def copy_rates_from(
    payload: CopyRatesFromRequest,
):
    """Get bars starting from the specified date."""
    # Enforce maximum count limit of 5,000
    capped_count = min(payload.count, 5000)
    params = {
        "symbol": payload.symbol,
        "timeframe": payload.timeframe.value,
        "date_from": datetime_to_timestamp(payload.date_from),
        "count": capped_count,
    }
    result = await run_mt5_op("copy_rates_from", params)
    if result is None:
        return CopyRatesResponse(rates=[])
    return CopyRatesResponse(rates=result)


@router.post(
    "/trade/market/book/add",
    response_model=MarketBookActionResponse,
)
async def market_book_add(
    payload: MarketBookRequest,
):
    """Subscribes the terminal to Market Depth change events for a specified symbol."""
    params = {"symbol": payload.symbol}
    result = await run_mt5_op("market_book_add", params)
    if result is False:
        raise HTTPException(status_code=400, detail="market_book_add failed")
    return MarketBookActionResponse(success=True)


@router.post(
    "/trade/market/book/release",
    response_model=MarketBookActionResponse,
)
async def market_book_release(
    payload: MarketBookRequest,
):
    """Unsubscribes the terminal from Market Depth change events
    for a specified symbol.
    """
    params = {"symbol": payload.symbol}
    result = await run_mt5_op("market_book_release", params)
    if result is False:
        raise HTTPException(status_code=400, detail="market_book_release failed")
    return MarketBookActionResponse(success=True)


@router.get(
    "/trade/market/book/get",
    response_model=MarketBookGetResponse,
)
async def market_book_get(
    symbol: str = Query(..., description="Symbol name"),
):
    """Returns a tuple of BookInfo objects containing market depth information."""
    params = {"symbol": symbol}
    result = await run_mt5_op("market_book_get", params)
    if result is None:
        return MarketBookGetResponse(items=[])
    return MarketBookGetResponse(items=result)


@router.post(
    "/trade/symbols/select",
    response_model=SymbolSelectResponse,
)
async def symbol_select(
    payload: SymbolSelectRequest,
):
    """Select a symbol in the Market Watch window."""
    params = payload.model_dump()
    result = await run_mt5_op("symbol_select", params)
    return SymbolSelectResponse(success=result)


@router.get(
    "/trade/symbols/total",
    response_model=SymbolsTotalResponse,
)
async def get_symbols_total():
    """Get the number of financial instruments."""
    result = await run_mt5_op("symbols_total", {})
    return SymbolsTotalResponse(total=result)


@router.get(
    "/trade/symbols",
    response_model=SymbolsGetResponse,
)
async def get_symbols(
    group: str | None = Query(None, description="Group name filter"),
):
    """Get all financial instruments (filterable by group)."""
    params = {}
    if group is not None:
        params["group"] = group
    result = await run_mt5_op("symbols_get", params)
    if result is None:
        return SymbolsGetResponse(symbols=[])
    return SymbolsGetResponse(symbols=result)


@router.post(
    "/trade/symbols/info",
    response_model=SymbolInfoResponse,
)
async def get_symbol_info(
    payload: SymbolInfoRequest,
):
    """Get data on a financial instrument."""
    params = payload.model_dump()
    result = await run_mt5_op("symbol_info", params)
    if result is None:
        raise HTTPException(
            status_code=404, detail=f"Symbol '{payload.symbol}' not found"
        )
    return SymbolInfoResponse(**result)


@router.post(
    "/trade/symbols/info/tick",
    response_model=TickResponse,
)
async def get_symbol_info_tick(
    payload: SymbolInfoTickRequest,
):
    """Get the last tick for a financial instrument."""
    params = payload.model_dump()
    result = await run_mt5_op("symbol_info_tick", params)
    if result is None:
        raise HTTPException(
            status_code=404, detail=f"Symbol tick '{payload.symbol}' not found"
        )
    return TickResponse(**result)


@router.post(
    "/trade/login",
    response_model=dict[str, Any],
)
async def login_broker(
    payload: AuthenticationRequest,
):
    """Log in programmatically to the broker account."""
    params = payload.model_dump(exclude_none=True)
    success = await run_mt5_op("login", params)
    if not success:
        err = mt5.last_error()
        raise HTTPException(
            status_code=400,
            detail=f"Login failed. Code: {err[0]}, Description: {err[1]}",
        )
    return {"success": True, "message": "Broker login successful"}
