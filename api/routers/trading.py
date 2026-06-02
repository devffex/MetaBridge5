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

    class MockMT5:
        def initialize(self, path=None, **kwargs):
            return True

        def shutdown(self):
            pass

        def login(self, login, password=None, server=None, timeout=None):
            return login != 999999

        def order_send(self, request, *args, **kwargs):
            class TradeRequestMock:
                def __init__(self, d):
                    self._d = d

                def _asdict(self):
                    return self._d

            class OrderSendResult:
                def _asdict(self):
                    return {
                        "retcode": 10009,
                        "deal": 535084512,
                        "order": 557416535,
                        "volume": request.get("volume", 0.0),
                        "price": request.get("price", 0.0),
                        "bid": 0.0,
                        "ask": 0.0,
                        "comment": "Mock success",
                        "request_id": 55,
                        "retcode_external": 0,
                        "request": TradeRequestMock(request),
                    }

            return OrderSendResult()

        def order_check(self, request, *args, **kwargs):
            class TradeRequestMock:
                def __init__(self, d):
                    self._d = d

                def _asdict(self):
                    return self._d

            class OrderCheckResult:
                def _asdict(self):
                    return {
                        "retcode": 0,
                        "balance": 10000.0,
                        "equity": 10000.0,
                        "profit": 0.0,
                        "margin": 100.0,
                        "margin_free": 9900.0,
                        "margin_level": 10000.0,
                        "comment": "Mock check success",
                        "request": TradeRequestMock(request),
                    }

            return OrderCheckResult()

        def order_calc_profit(
            self, action, symbol, volume, price_open, price_close, *args, **kwargs
        ):
            return 300.0

        def order_calc_margin(self, action, symbol, volume, price, *args, **kwargs):
            return 109.91

        def positions_get(self, *args, **kwargs):
            class Position:
                def _asdict(self):
                    return {
                        "ticket": 12345,
                        "time": 1705320000,
                        "time_msc": 1705320000000,
                        "time_update": 1705320000,
                        "time_update_msc": 1705320000000,
                        "type": 0,
                        "magic": 0,
                        "identifier": 12345,
                        "reason": 0,
                        "volume": 0.1,
                        "price_open": 1.1000,
                        "sl": 0.0,
                        "tp": 0.0,
                        "price_current": 1.1000,
                        "swap": 0.0,
                        "profit": 10.0,
                        "symbol": "EURUSD",
                        "comment": "Mock position",
                        "external_id": "",
                    }

            return [Position()]

        def positions_total(self, *args, **kwargs):
            return 1

        def terminal_info(self, *args, **kwargs):
            class Info:
                def _asdict(self):
                    return {
                        "community_account": True,
                        "community_connection": True,
                        "connected": True,
                        "dlls_allowed": False,
                        "trade_allowed": False,
                        "tradeapi_disabled": False,
                        "email_enabled": False,
                        "ftp_enabled": False,
                        "notifications_enabled": False,
                        "mqid": False,
                        "build": 2366,
                        "maxbars": 5000,
                        "codepage": 1251,
                        "ping_last": 77850,
                        "community_balance": 707.1,
                        "retransmission": 0.0,
                        "company": "MetaQuotes Software Corp.",
                        "name": "MetaTrader 5",
                        "language": "English",
                        "path": "C:\\MetaTrader5",
                        "data_path": "C:\\MetaTrader5",
                        "commondata_path": "C:\\Common",
                    }

            return Info()

        def account_info(self, *args, **kwargs):
            class Info:
                def _asdict(self):
                    return {
                        "login": 25115284,
                        "trade_mode": 0,
                        "leverage": 100,
                        "limit_orders": 200,
                        "margin_so_mode": 0,
                        "trade_allowed": True,
                        "trade_expert": True,
                        "margin_mode": 2,
                        "currency_digits": 2,
                        "fifo_close": False,
                        "balance": 99511.4,
                        "credit": 0.0,
                        "profit": 41.82,
                        "equity": 99553.22,
                        "margin": 98.18,
                        "margin_free": 99455.04,
                        "margin_level": 101398.67,
                        "margin_so_call": 50.0,
                        "margin_so_so": 30.0,
                        "margin_initial": 0.0,
                        "margin_maintenance": 0.0,
                        "assets": 0.0,
                        "liabilities": 0.0,
                        "commission_blocked": 0.0,
                        "name": "James Smith",
                        "server": "MetaQuotes-Demo",
                        "currency": "USD",
                        "company": "MetaQuotes Software Corp.",
                    }

            return Info()

        def history_deals_get(self, *args, **kwargs):
            class Deal:
                def _asdict(self):
                    return {
                        "ticket": 100,
                        "order": 100,
                        "time": 1705320000,
                        "time_msc": 1705320000000,
                        "type": 0,
                        "entry": 0,
                        "magic": 0,
                        "position_id": 100,
                        "reason": 0,
                        "volume": 0.1,
                        "price": 1.1000,
                        "commission": 0.0,
                        "swap": 0.0,
                        "profit": 10.0,
                        "fee": 0.0,
                        "symbol": "EURUSD",
                        "comment": "Mock deal",
                        "external_id": "",
                    }

            return [Deal()]

        def history_deals_total(self, *args, **kwargs):
            return 1

        def history_orders_get(self, *args, **kwargs):
            class Order:
                def _asdict(self):
                    return {
                        "ticket": 100,
                        "time_setup": 1705320000,
                        "time_setup_msc": 1705320000000,
                        "time_done": 1705320000,
                        "time_done_msc": 1705320000000,
                        "time_expiration": 0,
                        "type": 0,
                        "type_time": 0,
                        "type_filling": 0,
                        "state": 4,
                        "magic": 0,
                        "position_id": 100,
                        "position_by_id": 0,
                        "reason": 0,
                        "volume_initial": 0.1,
                        "volume_current": 0.0,
                        "price_open": 1.1000,
                        "sl": 0.0,
                        "tp": 0.0,
                        "price_current": 1.1000,
                        "price_stoplimit": 0.0,
                        "symbol": "EURUSD",
                        "comment": "Mock order",
                        "external_id": "",
                    }

            return [Order()]

        def history_orders_total(self, *args, **kwargs):
            return 1

        def orders_total(self, *args, **kwargs):
            return 1

        def orders_get(self, *args, **kwargs):
            return []

        def copy_ticks_range(
            self, symbol=None, date_from=None, date_to=None, flags=None, **kwargs
        ):
            return [
                {
                    "time": 1578614400,
                    "bid": 0.68577,
                    "ask": 0.68594,
                    "last": 0.0,
                    "volume": 0,
                    "time_msc": 1578614400820,
                    "flags": 134,
                    "volume_real": 0.0,
                }
            ]

        def copy_ticks_from(
            self, symbol=None, date_from=None, count=None, flags=None, **kwargs
        ):
            return [
                {
                    "time": 1578614400,
                    "bid": 1.11051,
                    "ask": 1.11069,
                    "last": 0.0,
                    "volume": 0,
                    "time_msc": 1578614400987,
                    "flags": 134,
                    "volume_real": 0.0,
                }
            ]

        def copy_rates_range(
            self, symbol=None, timeframe=None, date_from=None, date_to=None, **kwargs
        ):
            return [
                {
                    "time": 1578614400,
                    "open": 109.513,
                    "high": 109.527,
                    "low": 109.505,
                    "close": 109.521,
                    "tick_volume": 43,
                    "spread": 2,
                    "real_volume": 0,
                }
            ]

        def copy_rates_from_pos(
            self, symbol=None, timeframe=None, start_pos=None, count=None, **kwargs
        ):
            return [
                {
                    "time": 1581552000,
                    "open": 1.29568,
                    "high": 1.30692,
                    "low": 1.29441,
                    "close": 1.30412,
                    "tick_volume": 68228,
                    "spread": 0,
                    "real_volume": 0,
                }
            ]

        def copy_rates_from(
            self, symbol=None, timeframe=None, date_from=None, count=None, **kwargs
        ):
            return [
                {
                    "time": 1578484800,
                    "open": 1.11382,
                    "high": 1.11385,
                    "low": 1.11110,
                    "close": 1.11199,
                    "tick_volume": 9354,
                    "spread": 1,
                    "real_volume": 0,
                }
            ]

        def version(self):
            return (500, 4000, "15 Sep 2023")

        def last_error(self):
            return (0, "No error")

        def market_book_add(self, symbol=None, **kwargs):
            return True

        def market_book_release(self, symbol=None, **kwargs):
            return True

        def market_book_get(self, symbol=None, **kwargs):
            class BookInfoMock:
                def __init__(self, t, p, v, vd):
                    self.type = t
                    self.price = p
                    self.volume = v
                    self.volume_dbl = vd

                def _asdict(self):
                    return {
                        "type": self.type,
                        "price": self.price,
                        "volume": self.volume,
                        "volume_dbl": self.volume_dbl,
                    }

            return (BookInfoMock(1, 1.20038, 250, 250.0),)

        def symbol_select(self, symbol=None, enable=None, **kwargs):
            return True

        def symbol_info(self, symbol=None, **kwargs):
            class SymbolInfo:
                def _asdict(self):
                    return {
                        "custom": False,
                        "chart_mode": 0,
                        "select": True,
                        "visible": True,
                        "session_deals": 0,
                        "session_buy_orders": 0,
                        "session_sell_orders": 0,
                        "volume": 0,
                        "volumehigh": 0,
                        "volumelow": 0,
                        "time": 1585217595,
                        "digits": 5,
                        "spread": 39,
                        "spread_float": True,
                        "ticks_bookdepth": 10,
                        "trade_calc_mode": 0,
                        "trade_mode": 4,
                        "start_time": 0,
                        "expiration_time": 0,
                        "trade_stops_level": 0,
                        "trade_freeze_level": 0,
                        "trade_exemode": 1,
                        "swap_mode": 1,
                        "swap_rollover3days": 3,
                        "margin_hedged_use_leg": False,
                        "expiration_mode": 7,
                        "filling_mode": 1,
                        "order_mode": 127,
                        "order_gtc_mode": 0,
                        "option_mode": 0,
                        "option_right": 0,
                        "bid": 1.55192,
                        "bidhigh": 1.55842,
                        "bidlow": 1.54198,
                        "ask": 1.55231,
                        "askhigh": 1.55915,
                        "asklow": 1.54363,
                        "last": 0.0,
                        "lasthigh": 0.0,
                        "lastlow": 0.0,
                        "volume_real": 0.0,
                        "volumehigh_real": 0.0,
                        "volumelow_real": 0.0,
                        "option_strike": 0.0,
                        "point": 1e-05,
                        "trade_tick_value": 0.70,
                        "trade_tick_value_profit": 0.70,
                        "trade_tick_value_loss": 0.70,
                        "trade_tick_size": 1e-05,
                        "trade_contract_size": 100000.0,
                        "trade_accrued_interest": 0.0,
                        "trade_face_value": 0.0,
                        "trade_liquidity_rate": 0.0,
                        "volume_min": 0.01,
                        "volume_max": 500.0,
                        "volume_step": 0.01,
                        "volume_limit": 0.0,
                        "swap_long": -1.1,
                        "swap_short": -0.9,
                        "margin_initial": 0.0,
                        "margin_maintenance": 0.0,
                        "session_volume": 0.0,
                        "session_turnover": 0.0,
                        "session_interest": 0.0,
                        "session_buy_orders_volume": 0.0,
                        "session_sell_orders_volume": 0.0,
                        "session_open": 0.0,
                        "session_close": 0.0,
                        "session_aw": 0.0,
                        "session_price_settlement": 0.0,
                        "session_price_limit_min": 0.0,
                        "session_price_limit_max": 0.0,
                        "margin_hedged": 100000.0,
                        "price_change": 0.0,
                        "price_volatility": 0.0,
                        "price_theoretical": 0.0,
                        "price_greeks_delta": 0.0,
                        "price_greeks_theta": 0.0,
                        "price_greeks_gamma": 0.0,
                        "price_greeks_vega": 0.0,
                        "price_greeks_rho": 0.0,
                        "price_greeks_omega": 0.0,
                        "price_sensitivity": 0.0,
                        "basis": "",
                        "category": "",
                        "currency_base": "EUR",
                        "currency_profit": "CAD",
                        "currency_margin": "EUR",
                        "bank": "",
                        "description": "Euro vs Canadian Dollar",
                        "exchange": "",
                        "formula": "",
                        "isin": "",
                        "name": symbol,
                        "page": "",
                        "path": "",
                    }

            return SymbolInfo()

        def symbol_info_tick(self, symbol=None, **kwargs):
            class Tick:
                def _asdict(self):
                    return {
                        "time": 1585070338,
                        "bid": 1.17264,
                        "ask": 1.17279,
                        "last": 0.0,
                        "volume": 0,
                        "time_msc": 1585070338728,
                        "flags": 2,
                        "volume_real": 0.0,
                    }

            return Tick()

        def symbols_get(self, group=None, **kwargs):
            class SymInfo:
                def __init__(self, name, parent):
                    self._name = name
                    self._parent = parent

                def _asdict(self):
                    d = self._parent.symbol_info(self._name)._asdict()
                    d["name"] = self._name
                    d["path"] = f"Forex\\{self._name}"
                    return d

            return (
                SymInfo("EURUSD", self),
                SymInfo("GBPUSD", self),
                SymInfo("USDJPY", self),
            )

        def symbols_total(self, **kwargs):
            return 3

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
    op_func = getattr(mt5, op, None)
    if op_func is None:
        raise HTTPException(
            status_code=400, detail=f"Operation '{op}' not supported by MT5 API."
        )

    def _execute():
        if op == "order_calc_margin":
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


@router.post("/{org}/{trader}/{broker}/{account}/authenticate")
async def authenticate(
    org: str,
    trader: str,
    broker: str,
    account: str,
    payload: AuthenticationRequest,
):
    """Bridge switch account on the MetaTrader 5 terminal."""
    params = payload.model_dump(exclude_none=True)
    result = await run_mt5_op("login", params)
    if result is False:
        raise HTTPException(status_code=401, detail="Authentication failed")
    return {"status": "success", "message": f"Authenticated to account {payload.login}"}


@router.post(
    "/{org}/{trader}/{broker}/{account}/trade/order", response_model=OrderSendResult
)
async def send_order(
    org: str,
    trader: str,
    broker: str,
    account: str,
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
    "/{org}/{trader}/{broker}/{account}/trade/order/check",
    response_model=OrderCheckResult,
)
async def check_order(
    org: str,
    trader: str,
    broker: str,
    account: str,
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
    "/{org}/{trader}/{broker}/{account}/trade/order/calc/profit",
    response_model=OrderCalcProfitResponse,
)
async def calc_order_profit(
    org: str,
    trader: str,
    broker: str,
    account: str,
    payload: OrderCalcProfitRequest,
):
    """Estimate profit for a trading operation."""
    params = payload.model_dump()
    result = await run_mt5_op("order_calc_profit", params)
    if result is None:
        raise HTTPException(status_code=400, detail="Profit calculation failed.")
    return OrderCalcProfitResponse(profit=result)


@router.post(
    "/{org}/{trader}/{broker}/{account}/trade/order/calc/margin",
    response_model=OrderCalcMarginResponse,
)
async def calc_order_margin(
    org: str,
    trader: str,
    broker: str,
    account: str,
    payload: OrderCalcMarginRequest,
):
    """Estimate margin for a trading operation."""
    params = payload.model_dump()
    result = await run_mt5_op("order_calc_margin", params)
    if result is None:
        raise HTTPException(status_code=400, detail="Margin calculation failed.")
    return OrderCalcMarginResponse(margin=result)


@router.get(
    "/{org}/{trader}/{broker}/{account}/trade/positions",
    response_model=PositionsResponse,
)
async def get_positions(
    org: str,
    trader: str,
    broker: str,
    account: str,
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
    "/{org}/{trader}/{broker}/{account}/trade/positions/total",
    response_model=PositionsTotalResponse,
)
async def get_positions_total(
    org: str,
    trader: str,
    broker: str,
    account: str,
):
    """Get the number of active positions."""
    result = await run_mt5_op("positions_total", {})
    if result is None:
        return PositionsTotalResponse(total=0)
    return PositionsTotalResponse(total=result)


@router.get(
    "/{org}/{trader}/{broker}/{account}/trade/terminal/info",
    response_model=TerminalInfoResponse,
)
async def get_terminal_info(
    org: str,
    trader: str,
    broker: str,
    account: str,
):
    """Get the connected MetaTrader 5 client terminal status and settings."""
    result = await run_mt5_op("terminal_info", {})
    return TerminalInfoResponse(**result)


@router.get(
    "/{org}/{trader}/{broker}/{account}/trade/account",
    response_model=AccountInfoResponse,
)
async def get_account_info(
    org: str,
    trader: str,
    broker: str,
    account: str,
):
    """Get info on the current trading account."""
    result = await run_mt5_op("account_info", {})
    return AccountInfoResponse(**result)


@router.get(
    "/{org}/{trader}/{broker}/{account}/trade/version", response_model=VersionResponse
)
async def get_version(
    org: str,
    trader: str,
    broker: str,
    account: str,
):
    """Return the MetaTrader 5 terminal version."""
    result = await run_mt5_op("version", {})
    return VersionResponse(version=result[0], build=result[1], release_date=result[2])


@router.get(
    "/{org}/{trader}/{broker}/{account}/trade/last-error",
    response_model=LastErrorResponse,
)
async def get_last_error(
    org: str,
    trader: str,
    broker: str,
    account: str,
):
    """Return data on the last error."""
    result = await run_mt5_op("last_error", {})
    return LastErrorResponse(code=result[0], description=result[1])


@router.post(
    "/{org}/{trader}/{broker}/{account}/trade/history/deals",
    response_model=HistoryDealsResponse,
)
async def get_history_deals(
    org: str,
    trader: str,
    broker: str,
    account: str,
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
    "/{org}/{trader}/{broker}/{account}/trade/history/deals/total",
    response_model=HistoryDealsTotalResponse,
)
async def get_history_deals_total(
    org: str,
    trader: str,
    broker: str,
    account: str,
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
    "/{org}/{trader}/{broker}/{account}/trade/history/orders",
    response_model=HistoryOrdersResponse,
)
async def get_history_orders(
    org: str,
    trader: str,
    broker: str,
    account: str,
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
    "/{org}/{trader}/{broker}/{account}/trade/history/orders/total",
    response_model=HistoryOrdersTotalResponse,
)
async def get_history_orders_total(
    org: str,
    trader: str,
    broker: str,
    account: str,
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
    "/{org}/{trader}/{broker}/{account}/trade/orders/total",
    response_model=OrdersTotalResponse,
)
async def get_orders_total(
    org: str,
    trader: str,
    broker: str,
    account: str,
):
    """Get the number of active orders."""
    result = await run_mt5_op("orders_total", {})
    if result is None:
        return OrdersTotalResponse(total=0)
    return OrdersTotalResponse(total=result)


@router.get(
    "/{org}/{trader}/{broker}/{account}/trade/orders", response_model=OrdersGetResponse
)
async def get_orders(
    org: str,
    trader: str,
    broker: str,
    account: str,
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
    "/{org}/{trader}/{broker}/{account}/trade/market/ticks/range",
    response_model=CopyTicksResponse,
)
async def copy_ticks_range(
    org: str,
    trader: str,
    broker: str,
    account: str,
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
    return CopyTicksResponse(ticks=result)


@router.post(
    "/{org}/{trader}/{broker}/{account}/trade/market/ticks/from",
    response_model=CopyTicksResponse,
)
async def copy_ticks_from(
    org: str,
    trader: str,
    broker: str,
    account: str,
    payload: CopyTicksFromRequest,
):
    """Get ticks starting from the specified date."""
    params = {
        "symbol": payload.symbol,
        "date_from": datetime_to_timestamp(payload.date_from),
        "count": payload.count,
        "flags": payload.flags.value,
    }
    result = await run_mt5_op("copy_ticks_from", params)
    if result is None:
        return CopyTicksResponse(ticks=[])
    return CopyTicksResponse(ticks=result)


@router.post(
    "/{org}/{trader}/{broker}/{account}/trade/market/rates/range",
    response_model=CopyRatesResponse,
)
async def copy_rates_range(
    org: str,
    trader: str,
    broker: str,
    account: str,
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
    return CopyRatesResponse(rates=result)


@router.post(
    "/{org}/{trader}/{broker}/{account}/trade/market/rates/from-pos",
    response_model=CopyRatesResponse,
)
async def copy_rates_from_pos(
    org: str,
    trader: str,
    broker: str,
    account: str,
    payload: CopyRatesFromPosRequest,
):
    """Get bars from the specified index position."""
    params = {
        "symbol": payload.symbol,
        "timeframe": payload.timeframe.value,
        "start_pos": payload.start_pos,
        "count": payload.count,
    }
    result = await run_mt5_op("copy_rates_from_pos", params)
    if result is None:
        return CopyRatesResponse(rates=[])
    return CopyRatesResponse(rates=result)


@router.post(
    "/{org}/{trader}/{broker}/{account}/trade/market/rates/from",
    response_model=CopyRatesResponse,
)
async def copy_rates_from(
    org: str,
    trader: str,
    broker: str,
    account: str,
    payload: CopyRatesFromRequest,
):
    """Get bars starting from the specified date."""
    params = {
        "symbol": payload.symbol,
        "timeframe": payload.timeframe.value,
        "date_from": datetime_to_timestamp(payload.date_from),
        "count": payload.count,
    }
    result = await run_mt5_op("copy_rates_from", params)
    if result is None:
        return CopyRatesResponse(rates=[])
    return CopyRatesResponse(rates=result)


@router.post(
    "/{org}/{trader}/{broker}/{account}/trade/market/book/add",
    response_model=MarketBookActionResponse,
)
async def market_book_add(
    org: str,
    trader: str,
    broker: str,
    account: str,
    payload: MarketBookRequest,
):
    """Subscribes the terminal to Market Depth change events for a specified symbol."""
    params = {"symbol": payload.symbol}
    result = await run_mt5_op("market_book_add", params)
    if result is False:
        raise HTTPException(status_code=400, detail="market_book_add failed")
    return MarketBookActionResponse(success=True)


@router.post(
    "/{org}/{trader}/{broker}/{account}/trade/market/book/release",
    response_model=MarketBookActionResponse,
)
async def market_book_release(
    org: str,
    trader: str,
    broker: str,
    account: str,
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
    "/{org}/{trader}/{broker}/{account}/trade/market/book/get",
    response_model=MarketBookGetResponse,
)
async def market_book_get(
    org: str,
    trader: str,
    broker: str,
    account: str,
    symbol: str = Query(..., description="Symbol name"),
):
    """Returns a tuple of BookInfo objects containing market depth information."""
    params = {"symbol": symbol}
    result = await run_mt5_op("market_book_get", params)
    if result is None:
        return MarketBookGetResponse(items=[])
    return MarketBookGetResponse(items=result)


@router.post(
    "/{org}/{trader}/{broker}/{account}/trade/symbols/select",
    response_model=SymbolSelectResponse,
)
async def symbol_select(
    org: str,
    trader: str,
    broker: str,
    account: str,
    payload: SymbolSelectRequest,
):
    """Select a symbol in the Market Watch window."""
    params = payload.model_dump()
    result = await run_mt5_op("symbol_select", params)
    return SymbolSelectResponse(success=result)


@router.get(
    "/{org}/{trader}/{broker}/{account}/trade/symbols/total",
    response_model=SymbolsTotalResponse,
)
async def get_symbols_total(
    org: str,
    trader: str,
    broker: str,
    account: str,
):
    """Get the number of financial instruments."""
    result = await run_mt5_op("symbols_total", {})
    return SymbolsTotalResponse(total=result)


@router.get(
    "/{org}/{trader}/{broker}/{account}/trade/symbols",
    response_model=SymbolsGetResponse,
)
async def get_symbols(
    org: str,
    trader: str,
    broker: str,
    account: str,
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
    "/{org}/{trader}/{broker}/{account}/trade/symbols/info",
    response_model=SymbolInfoResponse,
)
async def get_symbol_info(
    org: str,
    trader: str,
    broker: str,
    account: str,
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
    "/{org}/{trader}/{broker}/{account}/trade/symbols/info/tick",
    response_model=TickResponse,
)
async def get_symbol_info_tick(
    org: str,
    trader: str,
    broker: str,
    account: str,
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
