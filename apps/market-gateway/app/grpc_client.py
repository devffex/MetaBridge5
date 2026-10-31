import json
import logging
import os
import sys

# Ensure the package directory is in sys.path so generated stubs can be imported
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import grpc
import terminal_pb2
import terminal_pb2_grpc

logger = logging.getLogger("market_gateway.grpc_client")


class TerminalGRPCClient:
    def __init__(self):
        host = os.environ.get("TERMINAL_GRPC_HOST")
        port = os.environ.get("TERMINAL_GRPC_PORT", "50051")
        if host:
            server_address = f"{host}:{port}"
        else:
            server_address = os.environ.get("MT5_GRPC_SERVER", "127.0.0.1:50051")
        self.api_key = os.environ.get("METABRIDGE5_API_KEY", "")

        logger.info(f"Connecting to MT5 gRPC server at {server_address}...")
        options = [
            ("grpc.max_send_message_length", 64 * 1024 * 1024),
            ("grpc.max_receive_message_length", 64 * 1024 * 1024),
            ("grpc.keepalive_time_ms", 10000),
            ("grpc.keepalive_timeout_ms", 5000),
            ("grpc.keepalive_permit_without_calls", 1),
            ("grpc.http2.max_pings_without_data", 0),
            ("grpc.initial_reconnect_backoff_ms", 50),
            ("grpc.max_reconnect_backoff_ms", 5000),
        ]
        self._connected = False
        self.channel = grpc.insecure_channel(server_address, options=options)
        self.channel.subscribe(self._on_channel_state_change, try_to_connect=True)
        self.stub = terminal_pb2_grpc.TerminalServiceStub(self.channel)

    def _on_channel_state_change(self, connectivity: grpc.ChannelConnectivity):
        self._connected = (connectivity == grpc.ChannelConnectivity.READY)
        logger.info(f"gRPC Channel connectivity changed to: {connectivity.name} (ready={self._connected})")

    @property
    def is_connected(self) -> bool:
        return self._connected

    def _get_metadata(self):
        if self.api_key:
            return [("x-api-key", self.api_key)]
        return []

    def resolve_symbol(self, symbol: str) -> str:
        """Resolves symbol casing and broker suffixes against the MT5 terminal symbols."""
        if not hasattr(self, "_symbol_map") or not self._symbol_map:
            try:
                syms = self.get_symbols(selected_only=False)
                m = {}
                for s in syms:
                    name = s.get("name", "")
                    if name:
                        m[name.upper()] = name
                        if name.endswith("m"):
                            base = name[:-1].upper()
                            if base not in m:
                                m[base] = name
                self._symbol_map = m
            except Exception as e:
                logger.warning(f"Could not build symbol resolution map: {e}")
                self._symbol_map = {}
        return self._symbol_map.get(symbol.upper(), symbol)

    def get_health(self):
        try:
            req = terminal_pb2.HealthRequest()
            res = self.stub.GetHealth(req, timeout=5)
            return {"status": res.status, "service": res.service}
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return {"status": "error", "message": str(e)}

    def get_rates_range(self, symbol: str, timeframe: int, date_from: str, date_to: str):
        try:
            resolved = self.resolve_symbol(symbol)
            req = terminal_pb2.RatesRangeRequest(
                symbol=resolved, timeframe=timeframe, date_from=date_from, date_to=date_to
            )
            res = self.stub.GetRatesRange(req, metadata=self._get_metadata(), timeout=60)
            return json.loads(res.rates_json)
        except Exception as e:
            logger.error(f"Failed to copy rates range for {symbol}: {e}")
            raise

    def get_rates_from(self, symbol: str, timeframe: int, date_from: str, count: int):
        try:
            resolved = self.resolve_symbol(symbol)
            req = terminal_pb2.RatesFromRequest(symbol=resolved, timeframe=timeframe, date_from=date_from, count=count)
            res = self.stub.GetRatesFrom(req, metadata=self._get_metadata(), timeout=60)
            return json.loads(res.rates_json)
        except Exception as e:
            logger.error(f"Failed to copy rates from for {symbol}: {e}")
            raise

    def get_rates_from_pos(self, symbol: str, timeframe: int, start_pos: int, count: int):
        try:
            resolved = self.resolve_symbol(symbol)
            req = terminal_pb2.RatesFromPosRequest(symbol=resolved, timeframe=timeframe, start_pos=start_pos, count=count)
            res = self.stub.GetRatesFromPos(req, metadata=self._get_metadata(), timeout=60)
            return json.loads(res.rates_json)
        except Exception as e:
            logger.error(f"Failed to copy rates from pos for {symbol}: {e}")
            raise

    def select_symbol(self, symbol: str, enable: bool):
        try:
            resolved = self.resolve_symbol(symbol)
            req = terminal_pb2.SymbolSelectRequest(symbol=resolved, enable=enable)
            res = self.stub.SelectSymbol(req, metadata=self._get_metadata(), timeout=15)
            return res.success
        except Exception as e:
            logger.error(f"Failed to select symbol {symbol}: {e}")
            raise

    def get_symbol_info_tick(self, symbol: str):
        try:
            resolved = self.resolve_symbol(symbol)
            req = terminal_pb2.SymbolRequest(symbol=resolved)
            res = self.stub.GetSymbolInfoTick(req, metadata=self._get_metadata(), timeout=5)
            if res.tick_json:
                return json.loads(res.tick_json)
            return None
        except Exception as e:
            logger.error(f"Failed to get tick info for {symbol}: {e}")
            raise

    def get_symbols(self, group: str = "", selected_only: bool = False):
        try:
            req = terminal_pb2.SymbolsRequest(group=group)
            res = self.stub.GetSymbols(req, metadata=self._get_metadata(), timeout=30)
            symbols = json.loads(res.symbols_json)
            if selected_only:
                return [s for s in symbols if s.get("visible") or s.get("select")]
            return symbols
        except Exception as e:
            logger.error(f"Failed to get symbols: {e}")
            raise

    def get_terminal_logs(self, lines: int = 100, date: str | None = None):
        try:
            req = terminal_pb2.TerminalLogsRequest(lines=lines, date=date or "")
            res = self.stub.GetTerminalLogs(req, metadata=self._get_metadata(), timeout=10)
            return {
                "file": res.file,
                "total_lines": res.total_lines,
                "returned_lines": res.returned_lines,
                "logs": list(res.content),
            }
        except Exception as e:
            logger.error(f"Failed to fetch terminal logs over gRPC: {e}")
            raise

    def close(self):
        self.channel.close()
