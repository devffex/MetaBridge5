import concurrent.futures
import json
import logging
import os
import sys
import threading
import time
from datetime import datetime

import grpc
import subprocess
from pathlib import Path
import psutil

# Setup basic logging to stdout
logging.basicConfig(
    level=logging.INFO,
    format="[gRPC Daemon] %(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("grpc_server")

# Ensure the script's directory is in sys.path so generated stubs can be imported
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Try to import generated protobuf stubs. During local development without codegen,
# we log a warning.
try:
    import terminal_pb2
    import terminal_pb2_grpc
except ImportError:
    logger.error(
        "Protobuf stubs not found. Run codegen first or verify paths.", exc_info=True
    )

    # Fallback placeholder to allow file compilation/inspection
    class MockProto:
        pass

    terminal_pb2 = MockProto()
    terminal_pb2_grpc = MockProto()
    terminal_pb2_grpc.TerminalServiceServicer = object

# ---------------------------------------------------------
# MetaTrader5 Fallback Import / Mocking
# ---------------------------------------------------------
try:
    if os.environ.get("METAFORGE_MOCK_MT5") == "1":
        raise ImportError("Mocking requested via environment variable")
    import MetaTrader5 as mt5
except ImportError:
    logger.warning("MetaTrader5 library not found. Using MockMT5 fallback.")

    class MockMT5:
        def __init__(self):
            self.last_err = (0, "Success")
            self.symbols = {
                "EURUSD": {"name": "EURUSD", "visible": True, "path": "Forex\\EURUSD"},
                "GBPUSD": {"name": "GBPUSD", "visible": True, "path": "Forex\\GBPUSD"},
                "USDJPY": {"name": "USDJPY", "visible": False, "path": "Forex\\USDJPY"},
                "AUDUSD": {"name": "AUDUSD", "visible": False, "path": "Forex\\AUDUSD"},
            }

        def initialize(self, *args, **kwargs):
            return True

        def shutdown(self):
            pass

        def last_error(self):
            return self.last_err

        def terminal_info(self):
            class Info:
                def __init__(self):
                    self.connected = True
                    self.build = 4320

                def _asdict(self):
                    return {"connected": self.connected, "build": self.build}

            return Info()

        def account_info(self):
            class Account:
                def __init__(self):
                    self.login = 123456
                    self.balance = 10000.0
                    self.currency = "USD"
                    self.company = "Mock Broker"

                def _asdict(self):
                    return {
                        "login": self.login,
                        "balance": self.balance,
                        "currency": self.currency,
                        "company": self.company,
                    }

            return Account()

        def positions_get(self, *args, **kwargs):
            return []

        def positions_total(self):
            return 0

        def orders_total(self):
            return 0

        def version(self):
            return (500, 4320, "2024-05-15")

        def order_send(self, request):
            return {"retcode": 10009, "comment": "Request executed", "order": 987654}

        def order_check(self, request):
            return {"retcode": 0, "comment": "Done"}

        def history_deals_get(self, *args, **kwargs):
            return []

        def history_deals_total(self, *args, **kwargs):
            return 0

        def history_orders_get(self, *args, **kwargs):
            return []

        def history_orders_total(self, *args, **kwargs):
            return 0

        def copy_ticks_from(self, *args, **kwargs):
            return []

        def copy_ticks_range(self, *args, **kwargs):
            return []

        def copy_rates_from(self, *args, **kwargs):
            return []

        def copy_rates_range(self, *args, **kwargs):
            return []

        def copy_rates_from_pos(self, symbol, timeframe, start_pos, count):
            symbol = symbol.upper()
            base_price = 1.08
            if "JPY" in symbol:
                base_price = 155.0
            elif "GBP" in symbol:
                base_price = 1.27
            
            # Simple timeframe duration in seconds
            tf_duration = 3600  # Default H1
            if timeframe <= 60:
                tf_duration = timeframe * 60
            elif timeframe == 16385:
                tf_duration = 3600
            elif timeframe == 16408:
                tf_duration = 86400
            elif timeframe == 32769:
                tf_duration = 7 * 86400
            elif timeframe == 49153:
                tf_duration = 30 * 86400
            
            import random
            # Seed with symbol and timeframe to make historical walk deterministic for visual testing
            random.seed(symbol + str(timeframe))
            
            now_sec = int(time.time())
            rates = []
            
            # Start walk
            current_close = base_price
            for i in range(count - 1, -1, -1):
                candle_time = now_sec - (i + start_pos) * tf_duration
                
                # Make random walk for prices
                change = random.normalvariate(0, 0.0005 * base_price)
                open_val = current_close
                close_val = current_close + change
                high_val = max(open_val, close_val) + abs(random.normalvariate(0, 0.0002 * base_price))
                low_val = min(open_val, close_val) - abs(random.normalvariate(0, 0.0002 * base_price))
                volume = int(random.random() * 500)
                
                rates.append({
                    "time": candle_time,
                    "open": round(open_val, 5),
                    "high": round(high_val, 5),
                    "low": round(low_val, 5),
                    "close": round(close_val, 5),
                    "tick_volume": volume
                })
                current_close = close_val
                
            return rates

        def market_book_add(self, *args, **kwargs):
            return True

        def market_book_release(self, *args, **kwargs):
            return True

        def market_book_get(self, *args, **kwargs):
            return []

        def symbol_select(self, symbol, enable):
            symbol = symbol.upper()
            if symbol in self.symbols:
                self.symbols[symbol]["visible"] = enable
                return True
            # Dynamically add if not exists
            self.symbols[symbol] = {"name": symbol, "visible": enable, "path": f"Forex\\{symbol}"}
            return True

        def symbols_total(self):
            return len(self.symbols)

        def symbols_get(self, group=""):
            # If group is specified, we can filter, but returning all is fine
            return list(self.symbols.values())

        def symbol_info(self, symbol):
            symbol = symbol.upper()
            if symbol in self.symbols:
                # Mock a basic symbol info class
                class SymbolInfo:
                    def __init__(self, name, visible):
                        self.name = name
                        self.visible = visible
                    def _asdict(self):
                        return {"name": self.name, "visible": self.visible}
                sym = self.symbols[symbol]
                return SymbolInfo(sym["name"], sym["visible"])
            return None

        def symbol_info_tick(self, symbol):
            symbol = symbol.upper()
            base_price = 1.08
            if "JPY" in symbol:
                base_price = 155.0
            elif "GBP" in symbol:
                base_price = 1.27
                
            import random
            jitter = random.normalvariate(0, 0.0001 * base_price)
            bid = base_price + jitter
            ask = bid + 0.00005 * base_price
            
            return {
                "time": int(time.time()),
                "bid": round(bid, 5),
                "ask": round(ask, 5),
                "last": round(bid, 5),
                "volume": int(random.random() * 5)
            }

        def login(self, *args, **kwargs):
            return True

        def order_calc_margin(self, *args, **kwargs):
            return 0.0

        def order_calc_profit(self, *args, **kwargs):
            return 0.0

    mt5 = MockMT5()

class SafeMT5Lock:
    def __init__(self):
        self._lock = threading.Lock()

    def acquire(self, blocking=True, timeout=-1):
        return self._lock.acquire(blocking, timeout)

    def release(self):
        self._lock.release()

    def __enter__(self):
        acquired = self._lock.acquire(timeout=10.0)
        if not acquired:
            raise RuntimeError("MT5 terminal lock timeout - terminal is busy or unresponsive")
        return True

    def __exit__(self, exc_type, exc_val, exc_tb):
        try:
            self._lock.release()
        except RuntimeError:
            pass

# Safe lock wrapper to serialize all operations that talk to the MT5 Windows API
mt5_lock = SafeMT5Lock()


# Helper to serialize MT5 namedtuples and numpy objects to JSON-compatible types
def _serialize_mt5(obj):
    if hasattr(obj, "dtype"):
        if getattr(obj.dtype, "names", None) is not None:
            names = obj.dtype.names
            return [{name: _serialize_mt5(row[name]) for name in names} for row in obj]
        elif hasattr(obj, "tolist"):
            val = obj.tolist()
            if isinstance(val, list):
                return [_serialize_mt5(i) for i in val]
            return val

    if hasattr(obj, "_asdict"):
        d = obj._asdict()
        return {k: _serialize_mt5(v) for k, v in d.items()}
    elif isinstance(obj, (list, tuple)):
        return [_serialize_mt5(i) for i in obj]
    elif isinstance(obj, dict):
        return {k: _serialize_mt5(v) for k, v in obj.items()}
    return obj


def parse_iso_datetime(val: str | None) -> int | None:
    if not val:
        return None
    try:
        val = val.replace("Z", "")
        if "T" in val:
            dt = datetime.fromisoformat(val)
        else:
            dt = datetime.strptime(val, "%Y-%m-%d %H:%M:%S")
        return int(dt.timestamp())
    except Exception as e:
        logger.error(f"Failed to parse datetime value '{val}': {e}")
        return None


def _find_terminal_process():
    for proc in psutil.process_iter(['pid', 'name']):
        try:
            if proc.info['name'] and 'terminal64.exe' in proc.info['name'].lower():
                return proc
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    return None


class APIKeyAuthInterceptor(grpc.ServerInterceptor):
    def __init__(self, api_key: str):
        self.api_key = api_key

    def intercept_service(self, continuation, handler_call_details):
        method = handler_call_details.method
        if "GetHealth" in method:
            return continuation(handler_call_details)

        metadata = dict(handler_call_details.invocation_metadata)
        client_key = metadata.get("x-api-key") or metadata.get("x-api-key-bin")
        if isinstance(client_key, bytes):
            client_key = client_key.decode("utf-8", errors="ignore")

        if not client_key or client_key != self.api_key:
            return self._abort_unauthenticated()

        return continuation(handler_call_details)

    def _abort_unauthenticated(self):
        def abort(request, context):
            context.abort(grpc.StatusCode.UNAUTHENTICATED, "Invalid or missing X-API-Key metadata header")
        return grpc.unary_unary_rpc_method_handler(abort)


_last_init_attempt = 0.0
_init_cooldown = 10.0  # seconds


class TerminalServiceServicer(terminal_pb2_grpc.TerminalServiceServicer):
    def _ensure_initialized_and_auth(self, context, bypass_auth=False):
        global _last_init_attempt
        # On-demand initialization
        info = mt5.terminal_info()
        if info is None:
            now = time.time()
            if now - _last_init_attempt < _init_cooldown:
                context.abort(
                    grpc.StatusCode.UNAVAILABLE,
                    "MT5 terminal connection is offline (cooldown active, please retry later)"
                )

            logger.info("Initializing MT5 terminal on-demand...")
            _last_init_attempt = now
            init_path = "M:\\MetaTrader5\\terminal64.exe" if os.path.exists("/opt/metabridge5/MetaTrader5/terminal64.exe") else "C:\\MetaTrader5\\terminal64.exe"
            if not mt5.initialize(path=init_path, portable=True, timeout=5000):
                err = mt5.last_error()
                context.abort(
                    grpc.StatusCode.UNAVAILABLE, f"MT5 initialization failed: {err}"
                )

        # Verification: terminals must be authenticated for data/trade endpoints
        if not bypass_auth:
            info = mt5.terminal_info()
            acct = mt5.account_info()
            if (
                info is None
                or not getattr(info, "connected", False)
                or acct is None
                or getattr(acct, "login", 0) == 0
            ):
                context.abort(
                    grpc.StatusCode.FAILED_PRECONDITION,
                    "Terminal not authenticated. Please log in manually to your broker account via VNC first.",
                )

    def GetHealth(self, request, context):
        return terminal_pb2.HealthResponse(status="ok", service="metabridge5-node-daemon")

    def GetTerminalInfo(self, request, context):
        with mt5_lock:
            self._ensure_initialized_and_auth(context, bypass_auth=True)
            info = mt5.terminal_info()
            if info is None:
                context.abort(
                    grpc.StatusCode.INTERNAL, "Failed to retrieve terminal info"
                )
            return terminal_pb2.TerminalInfoResponse(
                connected=getattr(info, "connected", False),
                build=getattr(info, "build", 0),
            )

    def GetAccountInfo(self, request, context):
        with mt5_lock:
            self._ensure_initialized_and_auth(context, bypass_auth=False)
            acct = mt5.account_info()
            if acct is None:
                context.abort(
                    grpc.StatusCode.INTERNAL, "Failed to retrieve account info"
                )
            return terminal_pb2.AccountInfoResponse(
                login=getattr(acct, "login", 0),
                balance=getattr(acct, "balance", 0.0),
                currency=getattr(acct, "currency", ""),
                company=getattr(acct, "company", ""),
            )

    def GetVersion(self, request, context):
        with mt5_lock:
            self._ensure_initialized_and_auth(context, bypass_auth=True)
            ver = mt5.version()
            if ver is None or len(ver) < 3:
                context.abort(grpc.StatusCode.INTERNAL, "Failed to retrieve version")
            return terminal_pb2.VersionResponse(
                version=ver[0], build=ver[1], release_date=ver[2]
            )

    def GetLastError(self, request, context):
        with mt5_lock:
            err = mt5.last_error()
            return terminal_pb2.ErrorResponse(code=err[0], description=err[1])

    def GetPositions(self, request, context):
        with mt5_lock:
            self._ensure_initialized_and_auth(context, bypass_auth=False)
            kwargs = {}
            if request.symbol:
                kwargs["symbol"] = request.symbol
            if request.ticket:
                kwargs["ticket"] = request.ticket
            res = mt5.positions_get(**kwargs)
            return terminal_pb2.PositionsResponse(
                positions_json=json.dumps(_serialize_mt5(res))
            )

    def GetPositionsTotal(self, request, context):
        with mt5_lock:
            self._ensure_initialized_and_auth(context, bypass_auth=False)
            total = mt5.positions_total()
            return terminal_pb2.TotalResponse(total=total)

    def GetOrders(self, request, context):
        with mt5_lock:
            self._ensure_initialized_and_auth(context, bypass_auth=False)
            kwargs = {}
            if request.symbol:
                kwargs["symbol"] = request.symbol
            if request.ticket:
                kwargs["ticket"] = request.ticket
            res = mt5.orders_get(**kwargs)
            return terminal_pb2.OrdersResponse(
                orders_json=json.dumps(_serialize_mt5(res))
            )

    def GetOrdersTotal(self, request, context):
        with mt5_lock:
            self._ensure_initialized_and_auth(context, bypass_auth=False)
            total = mt5.orders_total()
            return terminal_pb2.TotalResponse(total=total)

    def SendOrder(self, request, context):
        with mt5_lock:
            self._ensure_initialized_and_auth(context, bypass_auth=False)
            try:
                req_dict = json.loads(request.order_json)
            except Exception as e:
                context.abort(
                    grpc.StatusCode.INVALID_ARGUMENT, f"Invalid JSON order schema: {e}"
                )

            # Date conversions
            for k in ["expiration"]:
                if k in req_dict and isinstance(req_dict[k], str):
                    ts = parse_iso_datetime(req_dict[k])
                    if ts is not None:
                        req_dict[k] = ts

            res = mt5.order_send(req_dict)
            if res is None:
                context.abort(
                    grpc.StatusCode.INTERNAL, "Order execution failed (None returned)"
                )

            res_serialized = _serialize_mt5(res)
            retcode = getattr(res, "retcode", 999)
            comment = getattr(res, "comment", "Unknown error")
            order = getattr(res, "order", 0)
            return terminal_pb2.OrderActionResponse(
                retcode=retcode,
                comment=comment,
                order=order,
                result_json=json.dumps(res_serialized),
            )

    def CheckOrder(self, request, context):
        with mt5_lock:
            self._ensure_initialized_and_auth(context, bypass_auth=False)
            try:
                req_dict = json.loads(request.order_json)
            except Exception as e:
                context.abort(
                    grpc.StatusCode.INVALID_ARGUMENT, f"Invalid JSON order schema: {e}"
                )
            res = mt5.order_check(req_dict)
            if res is None:
                context.abort(
                    grpc.StatusCode.INTERNAL, "Order check failed (None returned)"
                )
            res_serialized = _serialize_mt5(res)
            return terminal_pb2.OrderCheckResponse(
                retcode=getattr(res, "retcode", 999),
                comment=getattr(res, "comment", "Unknown"),
                result_json=json.dumps(res_serialized),
            )

    def CalcProfit(self, request, context):
        with mt5_lock:
            self._ensure_initialized_and_auth(context, bypass_auth=False)
            val = mt5.order_calc_profit(
                request.action,
                request.symbol,
                request.volume,
                request.price_open,
                request.price_close,
            )
            if val is None:
                context.abort(grpc.StatusCode.INTERNAL, "Profit calculation failed")
            return terminal_pb2.CalcValueResponse(value=val)

    def CalcMargin(self, request, context):
        with mt5_lock:
            self._ensure_initialized_and_auth(context, bypass_auth=False)
            val = mt5.order_calc_margin(
                request.action, request.symbol, request.volume, request.price
            )
            if val is None:
                context.abort(grpc.StatusCode.INTERNAL, "Margin calculation failed")
            return terminal_pb2.CalcValueResponse(value=val)

    def Login(self, request, context):
        with mt5_lock:
            self._ensure_initialized_and_auth(context, bypass_auth=True)
            kwargs = {}
            if request.password:
                kwargs["password"] = request.password
            if request.server:
                kwargs["server"] = request.server
            success = mt5.login(request.login, **kwargs)
            return terminal_pb2.BoolResponse(success=bool(success))

    def GetHistoryDeals(self, request, context):
        with mt5_lock:
            self._ensure_initialized_and_auth(context, bypass_auth=False)
            dt_from = parse_iso_datetime(request.date_from)
            dt_to = parse_iso_datetime(request.date_to)

            kwargs = {}
            if request.ticket:
                kwargs["ticket"] = request.ticket
            elif request.position:
                try:
                    kwargs["position"] = int(request.position)
                except ValueError:
                    context.abort(
                        grpc.StatusCode.INVALID_ARGUMENT,
                        "position parameter must be numeric ticket ID",
                    )
            else:
                if dt_from is None or dt_to is None:
                    context.abort(
                        grpc.StatusCode.INVALID_ARGUMENT,
                        "date_from and date_to are required when querying history deals",
                    )
                kwargs["date_from"] = dt_from
                kwargs["date_to"] = dt_to

            res = mt5.history_deals_get(**kwargs)
            return terminal_pb2.HistoryDealsResponse(
                deals_json=json.dumps(_serialize_mt5(res))
            )

    def GetHistoryDealsTotal(self, request, context):
        with mt5_lock:
            self._ensure_initialized_and_auth(context, bypass_auth=False)
            dt_from = parse_iso_datetime(request.date_from)
            dt_to = parse_iso_datetime(request.date_to)
            if dt_from is None or dt_to is None:
                context.abort(
                    grpc.StatusCode.INVALID_ARGUMENT,
                    "date_from and date_to parameters are required",
                )
            total = mt5.history_deals_total(dt_from, dt_to)
            return terminal_pb2.TotalResponse(total=total)

    def GetHistoryOrders(self, request, context):
        with mt5_lock:
            self._ensure_initialized_and_auth(context, bypass_auth=False)
            dt_from = parse_iso_datetime(request.date_from)
            dt_to = parse_iso_datetime(request.date_to)

            kwargs = {}
            if request.ticket:
                kwargs["ticket"] = request.ticket
            elif request.position:
                try:
                    kwargs["position"] = int(request.position)
                except ValueError:
                    context.abort(
                        grpc.StatusCode.INVALID_ARGUMENT,
                        "position parameter must be numeric ticket ID",
                    )
            else:
                if dt_from is None or dt_to is None:
                    context.abort(
                        grpc.StatusCode.INVALID_ARGUMENT,
                        "date_from and date_to are required when querying history orders",
                    )
                kwargs["date_from"] = dt_from
                kwargs["date_to"] = dt_to

            res = mt5.history_orders_get(**kwargs)
            return terminal_pb2.HistoryOrdersResponse(
                orders_json=json.dumps(_serialize_mt5(res))
            )

    def GetHistoryOrdersTotal(self, request, context):
        with mt5_lock:
            self._ensure_initialized_and_auth(context, bypass_auth=False)
            dt_from = parse_iso_datetime(request.date_from)
            dt_to = parse_iso_datetime(request.date_to)
            if dt_from is None or dt_to is None:
                context.abort(
                    grpc.StatusCode.INVALID_ARGUMENT,
                    "date_from and date_to parameters are required",
                )
            total = mt5.history_orders_total(dt_from, dt_to)
            return terminal_pb2.TotalResponse(total=total)

    def GetTicksRange(self, request, context):
        with mt5_lock:
            self._ensure_initialized_and_auth(context, bypass_auth=False)
            dt_from = parse_iso_datetime(request.date_from)
            dt_to = parse_iso_datetime(request.date_to)
            if dt_from is None or dt_to is None:
                context.abort(
                    grpc.StatusCode.INVALID_ARGUMENT,
                    "date_from and date_to parameters are required",
                )
            res = mt5.copy_ticks_range(request.symbol, dt_from, dt_to, request.flags)
            return terminal_pb2.TicksResponse(
                ticks_json=json.dumps(_serialize_mt5(res))
            )

    def GetTicksFrom(self, request, context):
        with mt5_lock:
            self._ensure_initialized_and_auth(context, bypass_auth=False)
            dt_from = parse_iso_datetime(request.date_from)
            if dt_from is None:
                context.abort(
                    grpc.StatusCode.INVALID_ARGUMENT, "date_from parameter is required"
                )
            res = mt5.copy_ticks_from(
                request.symbol, dt_from, request.count, request.flags
            )
            return terminal_pb2.TicksResponse(
                ticks_json=json.dumps(_serialize_mt5(res))
            )

    def GetRatesRange(self, request, context):
        with mt5_lock:
            self._ensure_initialized_and_auth(context, bypass_auth=False)
            dt_from = parse_iso_datetime(request.date_from)
            dt_to = parse_iso_datetime(request.date_to)
            if dt_from is None or dt_to is None:
                context.abort(
                    grpc.StatusCode.INVALID_ARGUMENT,
                    "date_from and date_to parameters are required",
                )
            res = mt5.copy_rates_range(
                request.symbol, request.timeframe, dt_from, dt_to
            )
            return terminal_pb2.RatesResponse(
                rates_json=json.dumps(_serialize_mt5(res))
            )

    def GetRatesFromPos(self, request, context):
        with mt5_lock:
            self._ensure_initialized_and_auth(context, bypass_auth=False)
            res = mt5.copy_rates_from_pos(
                request.symbol, request.timeframe, request.start_pos, request.count
            )
            return terminal_pb2.RatesResponse(
                rates_json=json.dumps(_serialize_mt5(res))
            )

    def GetRatesFrom(self, request, context):
        with mt5_lock:
            self._ensure_initialized_and_auth(context, bypass_auth=False)
            dt_from = parse_iso_datetime(request.date_from)
            if dt_from is None:
                context.abort(
                    grpc.StatusCode.INVALID_ARGUMENT, "date_from parameter is required"
                )
            res = mt5.copy_rates_from(
                request.symbol, request.timeframe, dt_from, request.count
            )
            return terminal_pb2.RatesResponse(
                rates_json=json.dumps(_serialize_mt5(res))
            )

    def AddMarketBook(self, request, context):
        with mt5_lock:
            self._ensure_initialized_and_auth(context, bypass_auth=False)
            res = mt5.market_book_add(request.symbol)
            return terminal_pb2.BoolResponse(success=bool(res))

    def ReleaseMarketBook(self, request, context):
        with mt5_lock:
            self._ensure_initialized_and_auth(context, bypass_auth=False)
            res = mt5.market_book_release(request.symbol)
            return terminal_pb2.BoolResponse(success=bool(res))

    def GetMarketBook(self, request, context):
        with mt5_lock:
            self._ensure_initialized_and_auth(context, bypass_auth=False)
            res = mt5.market_book_get(request.symbol)
            return terminal_pb2.MarketBookResponse(
                items_json=json.dumps(_serialize_mt5(res))
            )

    def SelectSymbol(self, request, context):
        with mt5_lock:
            self._ensure_initialized_and_auth(context, bypass_auth=False)
            res = mt5.symbol_select(request.symbol, request.enable)
            return terminal_pb2.BoolResponse(success=bool(res))

    def GetSymbolsTotal(self, request, context):
        with mt5_lock:
            self._ensure_initialized_and_auth(context, bypass_auth=True)
            total = mt5.symbols_total()
            return terminal_pb2.TotalResponse(total=total)

    def GetSymbols(self, request, context):
        with mt5_lock:
            self._ensure_initialized_and_auth(context, bypass_auth=False)
            kwargs = {}
            if request.group:
                kwargs["group"] = request.group
            res = mt5.symbols_get(**kwargs)
            return terminal_pb2.SymbolsResponse(
                symbols_json=json.dumps(_serialize_mt5(res))
            )

    def GetSymbolInfo(self, request, context):
        with mt5_lock:
            self._ensure_initialized_and_auth(context, bypass_auth=False)
            res = mt5.symbol_info(request.symbol)
            return terminal_pb2.SymbolInfoResponse(
                info_json=json.dumps(_serialize_mt5(res))
            )

    def GetSymbolInfoTick(self, request, context):
        with mt5_lock:
            self._ensure_initialized_and_auth(context, bypass_auth=False)
            res = mt5.symbol_info_tick(request.symbol)
            return terminal_pb2.TickInfoResponse(
                tick_json=json.dumps(_serialize_mt5(res))
            )

    def StartTerminal(self, request, context):
        try:
            res = subprocess.run(["supervisorctl", "start", "wine"], capture_output=True, text=True)
            if res.returncode == 0 and "started" in res.stdout.lower():
                return terminal_pb2.BoolResponse(success=True)
        except Exception as e:
            logger.warning(f"Failed to start terminal via supervisorctl: {e}")
        
        proc = _find_terminal_process()
        if proc is not None:
            return terminal_pb2.BoolResponse(success=True)
        
        try:
            terminal_bin = "M:\\MetaTrader5\\terminal64.exe" if os.path.exists("/opt/metabridge5/MetaTrader5/terminal64.exe") else "C:\\MetaTrader5\\terminal64.exe"
            cmd = [terminal_bin, "/portable"]
            env = os.environ.copy()
            subprocess.Popen(cmd, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return terminal_pb2.BoolResponse(success=True)
        except Exception as e:
            logger.error(f"Failed to start terminal manually: {e}")
            context.abort(grpc.StatusCode.INTERNAL, f"Failed to start terminal: {e}")

    def StopTerminal(self, request, context):
        try:
            res = subprocess.run(["supervisorctl", "stop", "wine"], capture_output=True, text=True)
            if res.returncode == 0 and "stopped" in res.stdout.lower():
                return terminal_pb2.BoolResponse(success=True)
        except Exception as e:
            logger.warning(f"Failed to stop terminal via supervisorctl: {e}")
            
        proc = _find_terminal_process()
        if proc is None:
            return terminal_pb2.BoolResponse(success=True)
        
        try:
            parent = psutil.Process(proc.pid)
            for child in parent.children(recursive=True):
                child.kill()
            parent.kill()
            return terminal_pb2.BoolResponse(success=True)
        except Exception as e:
            logger.error(f"Failed to stop terminal manually: {e}")
            context.abort(grpc.StatusCode.INTERNAL, f"Failed to stop terminal: {e}")

    def GetTerminalStatus(self, request, context):
        proc = _find_terminal_process()
        if proc is not None:
            try:
                cpu = proc.cpu_percent(interval=0.1)
                mem = proc.memory_info().rss / (1024 * 1024)
                return terminal_pb2.TerminalStatusResponse(
                    status="running",
                    pid=proc.pid,
                    cpu_percent=cpu,
                    memory_rss_mb=mem
                )
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        return terminal_pb2.TerminalStatusResponse(
            status="stopped",
            pid=0,
            cpu_percent=0.0,
            memory_rss_mb=0.0
        )

    def GetTerminalLogs(self, request, context):
        logs_dir = Path("/opt/metabridge5/MetaTrader5/logs")
        if not logs_dir.exists():
            logs_dir = Path("/home/wine/.wine/drive_c/MetaTrader5/logs")
        if not logs_dir.exists():
            context.abort(grpc.StatusCode.NOT_FOUND, "Logs directory not found")
            
        log_files = sorted(logs_dir.glob("*.log"), reverse=True)
        terminal_logs = [f for f in log_files if f.name != "metaeditor.log"]
        if not terminal_logs:
            terminal_logs = log_files
            
        if not terminal_logs:
            context.abort(grpc.StatusCode.NOT_FOUND, "No log files found")
            
        target = terminal_logs[0]
        lines_count = request.lines if request.lines > 0 else 100
        
        try:
            with open(target, "r", encoding="utf-16-le", errors="replace") as f:
                all_lines = f.readlines()
        except Exception:
            try:
                with open(target, "r", encoding="utf-8", errors="replace") as f:
                    all_lines = f.readlines()
            except Exception as e:
                context.abort(grpc.StatusCode.INTERNAL, f"Failed to read log file: {e}")
                
        tail = all_lines[-lines_count:] if len(all_lines) > lines_count else all_lines
        content = [line.rstrip() for line in tail]
        
        return terminal_pb2.TerminalLogsResponse(
            file=target.name,
            total_lines=len(all_lines),
            returned_lines=len(tail),
            content=content
        )

    def DeployAsset(self, request, context):
        asset_type_map = {
            "ea": "Experts",
            "indicator": "Indicators",
            "script": "Scripts",
            "include": "Include",
            "library": "Libraries",
        }
        
        asset_type = request.asset_type.lower()
        if asset_type not in asset_type_map:
            return terminal_pb2.DeployAssetResponse(
                success=False,
                destination="",
                error=f"Invalid asset type '{request.asset_type}'. Valid types: {list(asset_type_map.keys())}"
            )
            
        base_mql5 = Path("/opt/metabridge5/MetaTrader5/MQL5") if Path("/opt/metabridge5/MetaTrader5").exists() else Path("/home/wine/.wine/drive_c/MetaTrader5/MQL5")
        target_dir = base_mql5 / asset_type_map[asset_type]
        try:
            target_dir.mkdir(parents=True, exist_ok=True)
            dest_path = target_dir / request.file_name
            
            with open(dest_path, "wb") as f:
                f.write(request.file_content)
                
            logger.info(f"Deployed asset {request.file_name} of type {request.asset_type} to {dest_path}")
            return terminal_pb2.DeployAssetResponse(
                success=True,
                destination=str(dest_path),
                error=""
            )
        except Exception as e:
            logger.error(f"Failed to deploy asset {request.file_name}: {e}")
            return terminal_pb2.DeployAssetResponse(
                success=False,
                destination="",
                error=str(e)
            )


def serve(port: int = 50051):
    api_key = os.environ.get("METABRIDGE5_API_KEY")
    interceptors = []
    if api_key:
        logger.info("Enabling API Key authentication interceptor")
        interceptors.append(APIKeyAuthInterceptor(api_key))
    else:
        logger.warning("METABRIDGE5_API_KEY environment variable not set. API Key authentication is DISABLED.")

    options = [
        ("grpc.max_send_message_length", 64 * 1024 * 1024),
        ("grpc.max_receive_message_length", 64 * 1024 * 1024),
    ]
    server = grpc.server(
        concurrent.futures.ThreadPoolExecutor(max_workers=1),
        interceptors=interceptors,
        options=options,
    )

    terminal_pb2_grpc.add_TerminalServiceServicer_to_server(
        TerminalServiceServicer(), server
    )
    server.add_insecure_port(f"[::]:{port}")
    logger.info(f"Starting gRPC server on port {port}...")
    server.start()

    # Graceful shutdown handler
    try:
        while True:
            time.sleep(86400)
    except KeyboardInterrupt:
        logger.info("Stopping gRPC server...")
        server.stop(0)
    finally:
        with mt5_lock:
            mt5.shutdown()
        logger.info("Server stopped.")


if __name__ == "__main__":
    port_arg = int(sys.argv[1]) if len(sys.argv) > 1 else 50051
    serve(port_arg)
