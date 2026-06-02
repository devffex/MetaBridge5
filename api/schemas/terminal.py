from pydantic import BaseModel


class AuthenticationRequest(BaseModel):
    login: int
    password: str
    server: str | None = None


class TerminalInfoResponse(BaseModel):
    """Response model for mt5.terminal_info() — 22 fields."""

    community_account: bool
    community_connection: bool
    connected: bool
    dlls_allowed: bool
    trade_allowed: bool
    tradeapi_disabled: bool
    email_enabled: bool
    ftp_enabled: bool
    notifications_enabled: bool
    mqid: bool
    build: int
    maxbars: int
    codepage: int
    ping_last: int
    community_balance: float
    retransmission: float
    company: str
    name: str
    language: str
    path: str
    data_path: str
    commondata_path: str


class AccountInfoResponse(BaseModel):
    """Response model for mt5.account_info() — 28 fields."""

    login: int
    trade_mode: int
    leverage: int
    limit_orders: int
    margin_so_mode: int
    trade_allowed: bool
    trade_expert: bool
    margin_mode: int
    currency_digits: int
    fifo_close: bool
    balance: float
    credit: float
    profit: float
    equity: float
    margin: float
    margin_free: float
    margin_level: float
    margin_so_call: float
    margin_so_so: float
    margin_initial: float
    margin_maintenance: float
    assets: float
    liabilities: float
    commission_blocked: float
    name: str
    server: str
    currency: str
    company: str


class VersionResponse(BaseModel):
    """Response model for mt5.version() — unpacked from (version, build, date) tuple."""

    version: int
    build: int
    release_date: str


class LastErrorResponse(BaseModel):
    """Response model for mt5.last_error() — unpacked from (code, description) tuple."""

    code: int
    description: str
