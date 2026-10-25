import asyncio
import logging
import time
from collections.abc import Awaitable, Callable
from dataclasses import asdict, dataclass
from typing import Any

logger = logging.getLogger("engine.candle0")

# Timeframe duration in seconds
TIMEFRAME_SECONDS = {
    "M1": 60,
    "M2": 120,
    "M3": 180,
    "M4": 240,
    "M5": 300,
    "M6": 360,
    "M10": 600,
    "M12": 720,
    "M15": 900,
    "M20": 1200,
    "M30": 1800,
    "H1": 3600,
    "H2": 7200,
    "H3": 10800,
    "H4": 14400,
    "H6": 21600,
    "H8": 28800,
    "H12": 43200,
    "D1": 86400,
    "W1": 604800,
    "MN1": 2592000,
}


@dataclass
class Candle0State:
    time: int
    open: float
    high: float
    low: float
    close: float
    tick_volume: int
    last_tick_time: int
    bid: float
    ask: float

    def to_compact_array(self) -> list[Any]:
        """
        Returns compact representation:
        [time, open, high, low, close, volume, bid, ask]
        """
        return [
            self.time,
            round(self.open, 5),
            round(self.high, 5),
            round(self.low, 5),
            round(self.close, 5),
            self.tick_volume,
            round(self.bid, 5),
            round(self.ask, 5),
        ]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class Candle0Manager:
    """
    Manages in-memory live Candle 0 calculation across active timeframes.
    Detects period boundary crossings, finalizes closed candles (Candle 1),
    and dispatches rollup callbacks to prevent data gaps.
    """

    def __init__(self, supported_timeframes: list[str] | None = None):
        self.supported_timeframes = supported_timeframes or ["M1", "M5", "M15", "M30", "H1", "H4", "D1", "W1", "MN1"]
        # (symbol, timeframe) -> Candle0State
        self._states: dict[tuple, Candle0State] = {}
        # Async callbacks when a candle closes: Callable[[symbol, timeframe, closed_candle_dict], Awaitable[None]]
        self._close_callbacks: list[Callable[[str, str, dict[str, Any]], Awaitable[None]]] = []
        self._lock = asyncio.Lock()
        logger.info(f"Initialized Candle0Manager with timeframes: {self.supported_timeframes}")

    def register_close_callback(self, callback: Callable[[str, str, dict[str, Any]], Awaitable[None]]):
        """Registers a callback function invoked when any candle period completes."""
        self._close_callbacks.append(callback)

    def _calculate_bucket_time(self, timestamp: int, tf_seconds: int) -> int:
        return timestamp - (timestamp % tf_seconds)

    async def process_tick(self, symbol: str, tick: dict[str, Any]) -> dict[str, Candle0State]:
        """
        Processes a raw tick from MT5 and updates all active timeframe Candle 0 states.
        Tick format expected: {"time": int, "bid": float, "ask": float, "last": float, "volume": int}
        """
        symbol = symbol.upper()
        tick_time = int(tick.get("time") or time.time())
        bid = float(tick.get("bid", 0.0))
        ask = float(tick.get("ask", 0.0))
        price = float(tick.get("last") or bid or ask)
        tick_vol = int(tick.get("volume", 1))

        if price <= 0.0:
            return {}

        updated_states: dict[str, Candle0State] = {}
        closed_candles: list[tuple] = []  # (symbol, tf, candle_dict)

        async with self._lock:
            for tf in self.supported_timeframes:
                tf_sec = TIMEFRAME_SECONDS.get(tf, 60)
                bucket_time = self._calculate_bucket_time(tick_time, tf_sec)
                state_key = (symbol, tf)

                current_state = self._states.get(state_key)

                if current_state is None:
                    # Initialize first candle 0
                    new_state = Candle0State(
                        time=bucket_time,
                        open=price,
                        high=price,
                        low=price,
                        close=price,
                        tick_volume=max(1, tick_vol),
                        last_tick_time=tick_time,
                        bid=bid,
                        ask=ask,
                    )
                    self._states[state_key] = new_state
                    updated_states[tf] = new_state
                elif bucket_time > current_state.time:
                    # Period rollover: current_state is closed!
                    closed_candle = current_state.to_dict()
                    closed_candles.append((symbol, tf, closed_candle))

                    # Initialize new Candle 0 for the new bucket
                    new_state = Candle0State(
                        time=bucket_time,
                        open=price,
                        high=price,
                        low=price,
                        close=price,
                        tick_volume=max(1, tick_vol),
                        last_tick_time=tick_time,
                        bid=bid,
                        ask=ask,
                    )
                    self._states[state_key] = new_state
                    updated_states[tf] = new_state
                else:
                    # In-flight candle update
                    current_state.high = max(current_state.high, price)
                    current_state.low = min(current_state.low, price)
                    current_state.close = price
                    current_state.tick_volume += max(1, tick_vol)
                    current_state.last_tick_time = tick_time
                    current_state.bid = bid
                    current_state.ask = ask
                    updated_states[tf] = current_state

        # Dispatch candle closed events asynchronously outside the lock
        for sym, tf, closed_candle in closed_candles:
            logger.info(f"Candle closed for {sym} {tf} at timestamp {closed_candle['time']}")
            for cb in self._close_callbacks:
                try:
                    asyncio.create_task(cb(sym, tf, closed_candle))
                except Exception as e:
                    logger.error(f"Error executing candle close callback for {sym} {tf}: {e}")

        return updated_states

    def get_candle0(self, symbol: str, timeframe: str) -> Candle0State | None:
        """Returns the current in-flight Candle 0 state for a given symbol and timeframe."""
        sym = symbol.upper()
        tf = timeframe.upper()
        if (sym, tf) in self._states:
            return self._states[(sym, tf)]
        if sym.endswith("M") and (sym[:-1], tf) in self._states:
            return self._states[(sym[:-1], tf)]
        if (sym + "M", tf) in self._states:
            return self._states[(sym + "M", tf)]
        return None

    def get_all_candle0(self, symbol: str) -> dict[str, dict[str, Any]]:
        """Returns all active timeframe Candle 0 states for a symbol."""
        sym = symbol.upper()
        target_sym = sym
        if (sym, "M1") not in self._states:
            if sym.endswith("M") and (sym[:-1], "M1") in self._states:
                target_sym = sym[:-1]
            elif (sym + "M", "M1") in self._states:
                target_sym = sym + "M"

        res = {}
        for tf in self.supported_timeframes:
            state = self._states.get((target_sym, tf))
            if state:
                res[tf] = state.to_dict()
        return res
