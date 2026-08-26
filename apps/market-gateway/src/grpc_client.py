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
        server_address = os.environ.get("MT5_GRPC_SERVER", "127.0.0.1:50051")
        self.api_key = os.environ.get("SAVISOR_API_KEY", "")

        logger.info(f"Connecting to MT5 gRPC server at {server_address}...")
        options = [
            ("grpc.max_send_message_length", 64 * 1024 * 1024),
            ("grpc.max_receive_message_length", 64 * 1024 * 1024),
        ]
        self.channel = grpc.insecure_channel(server_address, options=options)
        self.stub = terminal_pb2_grpc.TerminalServiceStub(self.channel)

    def _get_metadata(self):
        if self.api_key:
            return [("x-api-key", self.api_key)]
        return []

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
            req = terminal_pb2.RatesRangeRequest(
                symbol=symbol, timeframe=timeframe, date_from=date_from, date_to=date_to
            )
            res = self.stub.GetRatesRange(req, metadata=self._get_metadata(), timeout=60)
            return json.loads(res.rates_json)
        except Exception as e:
            logger.error(f"Failed to copy rates range for {symbol}: {e}")
            raise

    def get_rates_from(self, symbol: str, timeframe: int, date_from: str, count: int):
        try:
            req = terminal_pb2.RatesFromRequest(symbol=symbol, timeframe=timeframe, date_from=date_from, count=count)
            res = self.stub.GetRatesFrom(req, metadata=self._get_metadata(), timeout=60)
            return json.loads(res.rates_json)
        except Exception as e:
            logger.error(f"Failed to copy rates from for {symbol}: {e}")
            raise

    def get_rates_from_pos(self, symbol: str, timeframe: int, start_pos: int, count: int):
        try:
            req = terminal_pb2.RatesFromPosRequest(symbol=symbol, timeframe=timeframe, start_pos=start_pos, count=count)
            res = self.stub.GetRatesFromPos(req, metadata=self._get_metadata(), timeout=60)
            return json.loads(res.rates_json)
        except Exception as e:
            logger.error(f"Failed to copy rates from pos for {symbol}: {e}")
            raise

    def select_symbol(self, symbol: str, enable: bool):
        try:
            req = terminal_pb2.SymbolSelectRequest(symbol=symbol, enable=enable)
            res = self.stub.SelectSymbol(req, metadata=self._get_metadata(), timeout=15)
            return res.success
        except Exception as e:
            logger.error(f"Failed to select symbol {symbol}: {e}")
            raise

    def get_symbol_info_tick(self, symbol: str):
        try:
            req = terminal_pb2.SymbolRequest(symbol=symbol)
            res = self.stub.GetSymbolInfoTick(req, metadata=self._get_metadata(), timeout=5)
            if res.tick_json:
                return json.loads(res.tick_json)
            return None
        except Exception as e:
            logger.error(f"Failed to get tick info for {symbol}: {e}")
            raise

    def get_symbols(self, group: str = ""):
        try:
            req = terminal_pb2.SymbolsRequest(group=group)
            res = self.stub.GetSymbols(req, metadata=self._get_metadata(), timeout=30)
            return json.loads(res.symbols_json)
        except Exception as e:
            logger.error(f"Failed to get symbols: {e}")
            raise

    def close(self):
        self.channel.close()
