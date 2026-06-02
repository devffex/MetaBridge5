from enum import IntEnum


class TradeAction(IntEnum):
    DEAL = 1
    PENDING = 5
    SLTP = 6
    MODIFY = 7
    REMOVE = 8
    CLOSE_BY = 10


class OrderType(IntEnum):
    BUY = 0
    SELL = 1
    BUY_LIMIT = 2
    SELL_LIMIT = 3
    BUY_STOP = 4
    SELL_STOP = 5
    BUY_STOP_LIMIT = 6
    SELL_STOP_LIMIT = 7
    CLOSE_BY = 8


class OrderFilling(IntEnum):
    FOK = 0
    IOC = 1
    RETURN = 2


class OrderTypeTime(IntEnum):
    GTC = 0
    DAY = 1
    SPECIFIED = 2
    SPECIFIED_DAY = 3


class Timeframe(IntEnum):
    M1 = 1
    M2 = 2
    M3 = 3
    M4 = 4
    M5 = 5
    M6 = 6
    M10 = 10
    M12 = 12
    M15 = 15
    M20 = 20
    M30 = 30
    H1 = 16385
    H2 = 16386
    H3 = 16387
    H4 = 16388
    H6 = 16390
    H8 = 16392
    H12 = 16396
    D1 = 16408
    W1 = 16420
    MN1 = 16440


class CopyTicksFlag(IntEnum):
    ALL = -1
    INFO = 1
    TRADE = 2


class DealType(IntEnum):
    BUY = 0
    SELL = 1
    BALANCE = 2
    CREDIT = 3
    CHARGE = 4
    CORRECTION = 5
    BONUS = 6
    COMMISSION = 7
    COMMISSION_DAILY = 8
    COMMISSION_MONTHLY = 9
    COMMISSION_AGENT_DAILY = 10
    COMMISSION_AGENT_MONTHLY = 11
    INTEREST = 12
    BUY_CANCELED = 13
    SELL_CANCELED = 14
    DIVIDEND = 15
    DIVIDEND_FRANKED = 16
    TAX = 17


class DealEntry(IntEnum):
    IN = 0
    OUT = 1
    INOUT = 2
    OUT_BY = 3


class DealReason(IntEnum):
    CLIENT = 0
    MOBILE = 1
    WEB = 2
    EXPERT = 3
    SL = 4
    TP = 5
    SO = 6
    ROLLOVER = 7
    VMARGIN = 8
    SPLIT = 9


class OrderState(IntEnum):
    STARTED = 0
    PLACED = 1
    CANCELED = 2
    PARTIAL = 3
    FILLED = 4
    REJECTED = 5
    EXPIRED = 6
    REQUEST_ADD = 7
    REQUEST_MODIFY = 8
    REQUEST_CANCEL = 9


class PositionType(IntEnum):
    BUY = 0
    SELL = 1


class TickFlag(IntEnum):
    BID = 2
    ASK = 4
    LAST = 8
    VOLUME = 16
    BUY = 32
    SELL = 64


class BookType(IntEnum):
    SELL = 1
    BUY = 2
    SELL_MARKET = 3
    BUY_MARKET = 4
    SELL_STEP = 5
    BUY_STEP = 6
