"""
MT5 API Schemas
"""

from .base import datetime_to_timestamp, timestamp_to_datetime
from .enums import (
    BookType,
    CopyTicksFlag,
    DealEntry,
    DealReason,
    DealType,
    OrderFilling,
    OrderState,
    OrderType,
    OrderTypeTime,
    PositionType,
    TickFlag,
    Timeframe,
    TradeAction,
)
from .history import (
    DealResponse,
    HistoryDealsRequest,
    HistoryDealsResponse,
    HistoryDealsTotalRequest,
    HistoryDealsTotalResponse,
    HistoryOrdersRequest,
    HistoryOrdersResponse,
    HistoryOrdersTotalRequest,
    HistoryOrdersTotalResponse,
    OrderResponse,
)
from .market_data import (
    BookInfo,
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
    OrdersTotalResponse,
    RateResponse,
    TickResponse,
)
from .orders import (
    OrderCalcMarginRequest,
    OrderCalcMarginResponse,
    OrderCalcProfitRequest,
    OrderCalcProfitResponse,
    OrderCheckResult,
    OrderSendResult,
    TradeRequest,
)
from .positions import PositionResponse, PositionsResponse, PositionsTotalResponse
from .symbols import (
    SymbolInfoRequest,
    SymbolInfoResponse,
    SymbolInfoTickRequest,
    SymbolSelectRequest,
    SymbolSelectResponse,
    SymbolsGetResponse,
    SymbolsTotalResponse,
)
from .terminal import (
    AccountInfoResponse,
    LastErrorResponse,
    TerminalInfoResponse,
    VersionResponse,
)

__all__ = [
    "AccountInfoResponse",
    "BookInfo",
    "BookType",
    "CopyRatesFromPosRequest",
    "CopyRatesFromRequest",
    "CopyRatesRangeRequest",
    "CopyRatesResponse",
    "CopyTicksFlag",
    "CopyTicksFromRequest",
    "CopyTicksRangeRequest",
    "CopyTicksResponse",
    "DealEntry",
    "DealReason",
    # History
    "DealResponse",
    "DealType",
    "HistoryDealsRequest",
    "HistoryDealsResponse",
    "HistoryDealsTotalRequest",
    "HistoryDealsTotalResponse",
    "HistoryOrdersRequest",
    "HistoryOrdersResponse",
    "HistoryOrdersTotalRequest",
    "HistoryOrdersTotalResponse",
    "LastErrorResponse",
    "MarketBookActionResponse",
    "MarketBookGetResponse",
    "MarketBookRequest",
    "OrderCalcMarginRequest",
    "OrderCalcMarginResponse",
    "OrderCalcProfitRequest",
    "OrderCalcProfitResponse",
    "OrderCheckResult",
    "OrderFilling",
    "OrderResponse",
    "OrderSendResult",
    "OrderState",
    "OrderType",
    "OrderTypeTime",
    # Market data
    "OrdersTotalResponse",
    # Positions
    "PositionResponse",
    "PositionType",
    "PositionsResponse",
    "PositionsTotalResponse",
    "RateResponse",
    "SymbolInfoRequest",
    # Symbols
    "SymbolInfoResponse",
    "SymbolInfoTickRequest",
    "SymbolSelectRequest",
    "SymbolSelectResponse",
    "SymbolsGetResponse",
    "SymbolsTotalResponse",
    # Terminal
    "TerminalInfoResponse",
    "TickFlag",
    "TickResponse",
    "Timeframe",
    # Enums
    "TradeAction",
    # Orders
    "TradeRequest",
    "VersionResponse",
    "datetime_to_timestamp",
    "timestamp_to_datetime",
]
