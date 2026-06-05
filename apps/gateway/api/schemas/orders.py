from datetime import datetime

from pydantic import BaseModel

from schemas.enums import (
    OrderFilling,
    OrderType,
    OrderTypeTime,
    TradeAction,
)


class TradeRequest(BaseModel):
    action: TradeAction
    magic: int | None = None
    order: int | None = None
    symbol: str | None = None
    volume: float | None = None
    price: float | None = None
    stoplimit: float | None = None
    sl: float | None = None
    tp: float | None = None
    deviation: int | None = None
    type: OrderType | None = None
    type_filling: OrderFilling | None = None
    type_time: OrderTypeTime | None = None
    expiration: datetime | None = None
    comment: str | None = None
    position: int | None = None
    position_by: int | None = None


class OrderSendResult(BaseModel):
    retcode: int
    deal: int
    order: int
    volume: float
    price: float
    bid: float
    ask: float
    comment: str
    request_id: int
    retcode_external: int
    request: TradeRequest


class OrderCheckResult(BaseModel):
    retcode: int
    balance: float
    equity: float
    profit: float
    margin: float
    margin_free: float
    margin_level: float
    comment: str
    request: TradeRequest


class OrderCalcProfitRequest(BaseModel):
    action: OrderType
    symbol: str
    volume: float
    price_open: float
    price_close: float


class OrderCalcProfitResponse(BaseModel):
    profit: float


class OrderCalcMarginRequest(BaseModel):
    action: OrderType
    symbol: str
    volume: float
    price: float


class OrderCalcMarginResponse(BaseModel):
    margin: float
