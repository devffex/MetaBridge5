from datetime import datetime

from pydantic import BaseModel

from schemas.enums import BookType, CopyTicksFlag, Timeframe
from schemas.history import OrderResponse

# --- orders_total / orders_get ---


class OrdersTotalResponse(BaseModel):
    total: int


class OrdersGetResponse(BaseModel):
    orders: list[OrderResponse]


# --- Tick models ---


class TickResponse(BaseModel):
    time: int
    bid: float
    ask: float
    last: float
    volume: int
    time_msc: int
    flags: int
    volume_real: float


class CopyTicksRangeRequest(BaseModel):
    symbol: str
    date_from: datetime
    date_to: datetime
    flags: CopyTicksFlag


class CopyTicksFromRequest(BaseModel):
    symbol: str
    date_from: datetime
    count: int
    flags: CopyTicksFlag


class CopyTicksResponse(BaseModel):
    ticks: list[TickResponse]


# --- Rate models ---


class RateResponse(BaseModel):
    time: int
    open: float
    high: float
    low: float
    close: float
    tick_volume: int
    spread: int
    real_volume: int


class CopyRatesRangeRequest(BaseModel):
    symbol: str
    timeframe: Timeframe
    date_from: datetime
    date_to: datetime


class CopyRatesFromRequest(BaseModel):
    symbol: str
    timeframe: Timeframe
    date_from: datetime
    count: int


class CopyRatesFromPosRequest(BaseModel):
    symbol: str
    timeframe: Timeframe
    start_pos: int
    count: int


class CopyRatesResponse(BaseModel):
    rates: list[RateResponse]


# --- Market Book models ---


class MarketBookRequest(BaseModel):
    symbol: str


class BookInfo(BaseModel):
    type: BookType
    price: float
    volume: int
    volume_dbl: float


class MarketBookGetResponse(BaseModel):
    items: list[BookInfo]


class MarketBookActionResponse(BaseModel):
    success: bool
