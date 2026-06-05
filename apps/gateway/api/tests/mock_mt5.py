# ---------------------------------------------------------
# MockMT5 implementation for local testing and mock mode
# ---------------------------------------------------------


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
            def __init__(self):
                self.connected = True

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
            def __init__(self):
                self.login = 25115284

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
                    "ask": 1.55231,
                    "point": 1e-05,
                    "trade_tick_value": 0.70,
                    "trade_tick_value_profit": 0.70,
                    "trade_tick_value_loss": 0.70,
                    "trade_tick_size": 1e-05,
                    "trade_contract_size": 100000.0,
                    "volume_min": 0.01,
                    "volume_max": 500.0,
                    "volume_step": 0.01,
                    "swap_long": -1.1,
                    "swap_short": -0.9,
                    "name": symbol,
                    "description": "Euro vs Canadian Dollar",
                    "currency_base": "EUR",
                    "currency_profit": "CAD",
                    "currency_margin": "EUR",
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
