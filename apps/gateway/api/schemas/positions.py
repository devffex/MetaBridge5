from datetime import datetime

from pydantic import BaseModel

from schemas.enums import DealReason, PositionType


class PositionResponse(BaseModel):
    ticket: int
    time: datetime
    time_msc: int
    time_update: datetime
    time_update_msc: int
    type: PositionType
    magic: int
    identifier: int
    reason: DealReason
    volume: float
    price_open: float
    sl: float
    tp: float
    price_current: float
    swap: float
    profit: float
    symbol: str
    comment: str
    external_id: str


class PositionsResponse(BaseModel):
    positions: list[PositionResponse]


class PositionsTotalResponse(BaseModel):
    total: int
