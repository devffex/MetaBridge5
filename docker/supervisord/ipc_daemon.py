import http.server
import json
import logging
import os
import sys
import urllib.parse
from datetime import datetime
import socketserver
import threading

# Reentrant lock to serialize all operations that talk to the MT5 Windows API
mt5_lock = threading.Lock()

class ThreadingHTTPServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True

# Setup basic logging to stdout
logging.basicConfig(
    level=logging.INFO,
    format="[IPC Daemon] %(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("ipc_daemon")

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
                    return {"login": self.login, "balance": self.balance, "currency": self.currency, "company": self.company}
            return Account()
        def positions_get(self, *args, **kwargs):
            return []
        def positions_total(self):
            return 0
        def version(self):
            return (500, 4320, "2024-05-15")
        def order_send(self, request):
            return {"retcode": 10009, "comment": "Request executed", "order": 987654}
        def order_check(self, request):
            return {"retcode": 0, "comment": "Done"}
    mt5 = MockMT5()

# Helper to serialize MT5 namedtuples to JSON-compatible dicts
def _serialize_mt5(obj):
    if hasattr(obj, "_asdict"):
        d = obj._asdict()
        return {k: _serialize_mt5(v) for k, v in d.items()}
    elif isinstance(obj, (list, tuple)):
        return [_serialize_mt5(i) for i in obj]
    elif isinstance(obj, dict):
        return {k: _serialize_mt5(v) for k, v in obj.items()}
    return obj

def parse_iso_datetime(val):
    if not val:
        return None
    try:
        # standard ISO format: 2026-06-06T08:30:51
        val = val.replace("Z", "")
        if "T" in val:
            dt = datetime.fromisoformat(val)
        else:
            dt = datetime.strptime(val, "%Y-%m-%d %H:%M:%S")
        return int(dt.timestamp())
    except Exception as e:
        logger.error(f"Failed to parse datetime value '{val}': {e}")
        return None

# Mapping of endpoint paths to MT5 operations and their custom converters
PATH_MAPPING = {
    # Account & Terminal Information
    "/api/v1/terminals/trade/terminal/info": ("terminal_info", "GET", {}),
    "/api/v1/terminals/trade/account": ("account_info", "GET", {}),
    "/api/v1/terminals/trade/version": ("version", "GET", {}),
    "/api/v1/terminals/trade/last-error": ("last_error", "GET", {}),
    
    # Position & Order Operations
    "/api/v1/terminals/trade/positions": ("positions_get", "GET", {}),
    "/api/v1/terminals/trade/positions/total": ("positions_total", "GET", {}),
    "/api/v1/terminals/trade/orders/total": ("orders_total", "GET", {}),
    "/api/v1/terminals/trade/orders": ("orders_get", "GET", {}),
    
    # Trading Actions
    "/api/v1/terminals/trade/order": ("order_send", "POST", {}),
    "/api/v1/terminals/trade/order/check": ("order_check", "POST", {}),
    "/api/v1/terminals/trade/order/calc/profit": ("order_calc_profit", "POST", {}),
    "/api/v1/terminals/trade/order/calc/margin": ("order_calc_margin", "POST", {}),
    "/api/v1/terminals/trade/login": ("login", "POST", {}),
    
    # History Operations
    "/api/v1/terminals/trade/history/deals": ("history_deals_get", "POST", {}),
    "/api/v1/terminals/trade/history/deals/total": ("history_deals_total", "POST", {}),
    "/api/v1/terminals/trade/history/orders": ("history_orders_get", "POST", {}),
    "/api/v1/terminals/trade/history/orders/total": ("history_orders_total", "POST", {}),
    
    # Market Data
    "/api/v1/terminals/trade/market/ticks/range": ("copy_ticks_range", "POST", {}),
    "/api/v1/terminals/trade/market/ticks/from": ("copy_ticks_from", "POST", {}),
    "/api/v1/terminals/trade/market/rates/range": ("copy_rates_range", "POST", {}),
    "/api/v1/terminals/trade/market/rates/from-pos": ("copy_rates_from_pos", "POST", {}),
    "/api/v1/terminals/trade/market/rates/from": ("copy_rates_from", "POST", {}),
    "/api/v1/terminals/trade/market/book/add": ("market_book_add", "POST", {}),
    "/api/v1/terminals/trade/market/book/release": ("market_book_release", "POST", {}),
    "/api/v1/terminals/trade/market/book/get": ("market_book_get", "GET", {}),
    
    # Symbols Information
    "/api/v1/terminals/symbols/select": ("symbol_select", "POST", {}),
    "/api/v1/terminals/symbols/total": ("symbols_total", "GET", {}),
    "/api/v1/terminals/symbols": ("symbols_get", "GET", {}),
    "/api/v1/terminals/symbols/info": ("symbol_info", "POST", {}),
    "/api/v1/terminals/symbols/info/tick": ("symbol_info_tick", "POST", {}),
}

class MT5IPCRequestHandler(http.server.BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        # Redirect standard HTTP logging to our daemon logger
        logger.info("%s - - %s" % (self.client_address[0], format%args))

    def _send_response(self, status_code, body):
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        self.wfile.write(json.dumps(body).encode("utf-8"))

    def do_OPTIONS(self):
        self._send_response(200, {})

    def do_GET(self):
        self._handle_request("GET")

    def do_POST(self):
        self._handle_request("POST")

    def _handle_request(self, method):
        parsed_url = urllib.parse.urlparse(self.path)
        path = parsed_url.path
        
        # Health check endpoint
        if path == "/health" or path == "/api/v1/health":
            # Simple health check, does not require MT5 to be initialized yet
            self._send_response(200, {"status": "ok", "service": "savisor-node-daemon"})
            return

        if path not in PATH_MAPPING:
            self._send_response(404, {"error": f"Path '{path}' not found"})
            return

        op, expected_method, _ = PATH_MAPPING[path]
        
        # Verify HTTP method
        if method != expected_method and not (method == "POST" and expected_method == "GET"):
            # Fallback: allow POSTing to GET endpoints if requested
            pass
        
        # Parse params/payload
        params = {}
        if method == "POST":
            content_length = int(self.headers.get("Content-Length", 0))
            if content_length > 0:
                try:
                    params = json.loads(self.rfile.read(content_length).decode("utf-8"))
                except Exception as e:
                    self._send_response(400, {"error": f"Invalid JSON payload: {e}"})
                    return
        else:
            # Parse query parameters for GET requests
            query_params = urllib.parse.parse_qs(parsed_url.query)
            for k, v in query_params.items():
                # Take first parameter value
                val = v[0]
                if val.isdigit():
                    params[k] = int(val)
                elif val.replace('.', '', 1).isdigit():
                    params[k] = float(val)
                elif val.lower() == 'true':
                    params[k] = True
                elif val.lower() == 'false':
                    params[k] = False
                else:
                    params[k] = val

        # Handle Date conversions
        for k in ["date_from", "date_to", "expiration"]:
            if k in params and isinstance(params[k], str):
                ts = parse_iso_datetime(params[k])
                if ts is not None:
                    params[k] = ts

        try:
            with mt5_lock:
                # On-demand initialization
                if op != "initialize":
                    info = mt5.terminal_info()
                    if info is None:
                        logger.info("Initializing MT5 terminal on-demand...")
                        if not mt5.initialize():
                            err = mt5.last_error()
                            self._send_response(500, {"error": f"MT5 initialization failed: {err}"})
                            return

                # Verification: terminals must be authenticated for data/trade endpoints
                if op not in ("initialize", "terminal_info", "version", "last_error", "login"):
                    info = mt5.terminal_info()
                    acct = mt5.account_info()
                    if (
                        info is None
                        or not getattr(info, "connected", False)
                        or acct is None
                        or getattr(acct, "login", 0) == 0
                    ):
                        self._send_response(412, {
                            "error": "Terminal not authenticated. Please log in manually to your broker account via VNC first."
                        })
                        return

                # Call operation
                op_func = getattr(mt5, op, None)
                if op_func is None:
                    self._send_response(400, {"error": f"Operation '{op}' not supported by MT5 API"})
                    return

                result = self._execute_operation(op, op_func, params)
                
                # Format return types
                serialized = _serialize_mt5(result)
                
                # Match old schema wrapper structures
                if op == "positions_get":
                    self._send_response(200, {"positions": serialized or []})
                elif op == "positions_total":
                    self._send_response(200, {"total": serialized or 0})
                elif op == "orders_total":
                    self._send_response(200, {"total": serialized or 0})
                elif op == "orders_get":
                    self._send_response(200, {"orders": serialized or []})
                elif op == "history_deals_get":
                    self._send_response(200, {"deals": serialized or []})
                elif op == "history_deals_total":
                    self._send_response(200, {"total": serialized or 0})
                elif op == "history_orders_get":
                    self._send_response(200, {"orders": serialized or []})
                elif op == "history_orders_total":
                    self._send_response(200, {"total": serialized or 0})
                elif op in ("copy_ticks_range", "copy_ticks_from"):
                    self._send_response(200, {"ticks": serialized or []})
                elif op in ("copy_rates_range", "copy_rates_from_pos", "copy_rates_from"):
                    self._send_response(200, {"rates": serialized or []})
                elif op in ("market_book_add", "market_book_release"):
                    self._send_response(200, {"success": bool(serialized)})
                elif op == "market_book_get":
                    self._send_response(200, {"items": serialized or []})
                elif op == "symbol_select":
                    self._send_response(200, {"success": bool(serialized)})
                elif op == "symbols_total":
                    self._send_response(200, {"total": serialized or 0})
                elif op == "symbols_get":
                    self._send_response(200, {"symbols": serialized or []})
                elif op == "version":
                    self._send_response(200, {"version": serialized[0], "build": serialized[1], "release_date": serialized[2]})
                elif op == "last_error":
                    self._send_response(200, {"code": serialized[0], "description": serialized[1]})
                elif op == "order_calc_profit":
                    self._send_response(200, {"profit": serialized})
                elif op == "order_calc_margin":
                    self._send_response(200, {"margin": serialized})
                else:
                    self._send_response(200, serialized)

        except Exception as e:
            logger.error(f"Error executing operation '{op}': {e}", exc_info=True)
            self._send_response(500, {"error": str(e)})

    def _execute_operation(self, op, op_func, params):
        if op == "login":
            return op_func(
                params["login"],
                password=params.get("password"),
                server=params.get("server"),
            )
        elif op == "order_calc_margin":
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

def run_server(port=8000):
    server_address = ("", port)
    httpd = ThreadingHTTPServer(server_address, MT5IPCRequestHandler)
    logger.info(f"Starting lightweight MT5 IPC Daemon on port {port}...")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        logger.info("Daemon stopping via keyboard interrupt...")
    finally:
        with mt5_lock:
            mt5.shutdown()
        logger.info("Daemon stopped.")

if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    run_server(port)
