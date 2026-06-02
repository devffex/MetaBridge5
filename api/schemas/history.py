from datetime import datetime

from pydantic import BaseModel, field_validator, model_validator

from schemas.enums import (
    DealEntry,
    DealReason,
    DealType,
    OrderFilling,
    OrderState,
    OrderType,
    OrderTypeTime,
)


class DealResponse(BaseModel):
    ticket: int
    order: int
    time: datetime
    time_msc: int
    type: DealType
    entry: DealEntry
    magic: int
    position_id: int
    reason: DealReason
    volume: float
    price: float
    commission: float
    swap: float
    profit: float
    fee: float
    symbol: str
    comment: str
    external_id: str


class HistoryDealsResponse(BaseModel):
    deals: list[DealResponse]


class HistoryDealsRequest(BaseModel):
    date_from: datetime | None = None
    date_to: datetime | None = None
    group: str | None = None
    ticket: int | None = None
    position: int | None = None

    @model_validator(mode="after")
    def validate_mutually_exclusive(self) -> "HistoryDealsRequest":
        has_date_from = self.date_from is not None
        has_date_to = self.date_to is not None
        has_dates = has_date_from and has_date_to
        has_ticket = self.ticket is not None
        has_position = self.position is not None

        # Catch partial date specification
        if has_date_from != has_date_to:
            raise ValueError("Both date_from and date_to must be provided together.")

        # Count how many parameter sets are provided
        provided_sets = sum([has_dates, has_ticket, has_position])

        if provided_sets == 0:
            raise ValueError(
                "Must provide either (date_from, date_to), ticket, or position."
            )
        elif provided_sets > 1:
            raise ValueError(
                "Parameters (date_from, date_to), ticket, and position "
                "are mutually exclusive."
            )

        if self.group is not None and not has_dates:
            raise ValueError(
                "The 'group' parameter can only be used with date_from and date_to."
            )

        return self


class HistoryDealsTotalRequest(BaseModel):
    date_from: datetime
    date_to: datetime


class HistoryDealsTotalResponse(BaseModel):
    total: int


class OrderResponse(BaseModel):
    ticket: int
    time_setup: datetime
    time_setup_msc: int
    time_done: datetime
    time_done_msc: int
    time_expiration: datetime | None = None
    type: OrderType
    type_time: OrderTypeTime
    type_filling: OrderFilling
    state: OrderState
    magic: int
    position_id: int
    position_by_id: int
    reason: DealReason
    volume_initial: float
    volume_current: float
    price_open: float
    sl: float
    tp: float
    price_current: float
    price_stoplimit: float
    symbol: str
    comment: str
    external_id: str

    @field_validator("time_expiration", mode="before")
    @classmethod
    def zero_expiration_to_none(cls, v):
        """MT5 returns 0 for 'no expiration' — coerce to None."""
        if v == 0:
            return None
        return v


class HistoryOrdersResponse(BaseModel):
    orders: list[OrderResponse]


class HistoryOrdersRequest(BaseModel):
    date_from: datetime | None = None
    date_to: datetime | None = None
    group: str | None = None
    ticket: int | None = None
    position: int | None = None

    @model_validator(mode="after")
    def validate_mutually_exclusive(self) -> "HistoryOrdersRequest":
        has_date_from = self.date_from is not None
        has_date_to = self.date_to is not None
        has_dates = has_date_from and has_date_to
        has_ticket = self.ticket is not None
        has_position = self.position is not None

        # Catch partial date specification
        if has_date_from != has_date_to:
            raise ValueError("Both date_from and date_to must be provided together.")

        provided_sets = sum([has_dates, has_ticket, has_position])

        if provided_sets == 0:
            raise ValueError(
                "Must provide either (date_from, date_to), ticket, or position."
            )
        elif provided_sets > 1:
            raise ValueError(
                "Parameters (date_from, date_to), ticket, and position "
                "are mutually exclusive."
            )

        if self.group is not None and not has_dates:
            raise ValueError(
                "The 'group' parameter can only be used with date_from and date_to."
            )

        return self


class HistoryOrdersTotalRequest(BaseModel):
    date_from: datetime
    date_to: datetime


class HistoryOrdersTotalResponse(BaseModel):
    total: int
