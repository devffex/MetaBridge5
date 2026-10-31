from __future__ import annotations

import io
import json
import logging
from typing import Any

import arro3.core as ac
import arro3.io as aio

logger = logging.getLogger("pipeline.parquet_exporter")

CANDLE_COLUMNS = ["time", "open", "high", "low", "close", "tick_volume"]


class _IlocIndexer:
    def __init__(self, frame: CandleFrame):
        self._frame = frame

    def __getitem__(self, idx: int | slice) -> dict[str, Any] | CandleFrame:
        if isinstance(idx, slice):
            return CandleFrame(self._frame._records[idx])
        return self._frame._records[idx]


class _ValuesWrapper:
    def __init__(self, records: list[dict[str, Any]]):
        self._records = records

    def tolist(self) -> list[list[Any]]:
        return [
            [
                int(r["time"]),
                float(r["open"]),
                float(r["high"]),
                float(r["low"]),
                float(r["close"]),
                int(r.get("tick_volume", 0)),
            ]
            for r in self._records
        ]


class CandleFrame:
    """
    Lightweight, high-performance in-memory candle table replacing pandas/pyarrow.
    Provides dict-like indexer compatibility (.iloc, .columns, len()) and zero-copy
    conversions to compact JSON and Apache Parquet via arro3.
    """

    def __init__(self, records: list[dict[str, Any]] | None = None):
        self._records: list[dict[str, Any]] = list(records) if records else []

    @property
    def columns(self) -> list[str]:
        return list(CANDLE_COLUMNS)

    def __len__(self) -> int:
        return len(self._records)

    def __getitem__(self, key: Any) -> Any:
        if isinstance(key, list):
            return self
        if isinstance(key, str):
            return [r.get(key) for r in self._records]
        raise TypeError(f"Invalid CandleFrame subscription key: {key}")

    @property
    def iloc(self) -> _IlocIndexer:
        return _IlocIndexer(self)

    @property
    def values(self) -> _ValuesWrapper:
        return _ValuesWrapper(self._records)

    def to_compact_json_bytes(self, limit: int | None = None) -> bytes:
        if limit is not None and limit > 0 and len(self._records) > limit:
            selected = self._records[-limit:]
        else:
            selected = self._records

        formatted = [
            [
                int(r["time"]),
                round(float(r["open"]), 5),
                round(float(r["high"]), 5),
                round(float(r["low"]), 5),
                round(float(r["close"]), 5),
                int(r.get("tick_volume", 0)),
            ]
            for r in selected
        ]
        return json.dumps(formatted, separators=(",", ":")).encode("utf-8")

    def to_arrow_table(self) -> ac.Table:
        times = [int(r["time"]) for r in self._records]
        opens = [float(r["open"]) for r in self._records]
        highs = [float(r["high"]) for r in self._records]
        lows = [float(r["low"]) for r in self._records]
        closes = [float(r["close"]) for r in self._records]
        volumes = [int(r.get("tick_volume", 0)) for r in self._records]

        data = {
            "time": ac.Array(times, type=ac.DataType.int64()),
            "open": ac.Array(opens, type=ac.DataType.float64()),
            "high": ac.Array(highs, type=ac.DataType.float64()),
            "low": ac.Array(lows, type=ac.DataType.float64()),
            "close": ac.Array(closes, type=ac.DataType.float64()),
            "tick_volume": ac.Array(volumes, type=ac.DataType.int64()),
        }
        return ac.Table.from_pydict(data)


def rates_to_dataframe(rates: list[dict[str, Any]] | CandleFrame) -> CandleFrame:
    """
    Converts MT5 rates list into a normalized, sorted, and deduplicated CandleFrame.
    Preserves last-write-wins semantics for duplicate timestamps.
    """
    if isinstance(rates, CandleFrame):
        return rates

    if not rates:
        return CandleFrame([])

    by_time: dict[int, dict[str, Any]] = {}
    for r in rates:
        # Standardize volume naming
        raw_vol = r.get("tick_volume") if "tick_volume" in r else r.get("volume", 0)

        # Validate required fields
        for req in ("time", "open", "high", "low", "close"):
            if req not in r:
                raise ValueError(f"Missing required candle column: {req}")

        t = int(r["time"])
        by_time[t] = {
            "time": t,
            "open": float(r["open"]),
            "high": float(r["high"]),
            "low": float(r["low"]),
            "close": float(r["close"]),
            "tick_volume": int(raw_vol),
        }

    sorted_records = [by_time[t] for t in sorted(by_time.keys())]
    return CandleFrame(sorted_records)


def dataframe_to_parquet_bytes(df: CandleFrame, compression: str = "snappy") -> bytes:
    """
    Serializes CandleFrame into compressed Apache Parquet binary bytes using arro3.
    """
    table = df.to_arrow_table()
    buf = io.BytesIO()
    aio.write_parquet(table, buf, compression=compression)
    return buf.getvalue()


def parquet_bytes_to_dataframe(data: bytes) -> CandleFrame:
    """
    Reads Parquet bytes into a CandleFrame using arro3.
    """
    buf = io.BytesIO(data)
    reader = aio.read_parquet(buf)
    table = reader.read_all()

    times = table.column("time").to_pylist()
    opens = table.column("open").to_pylist()
    highs = table.column("high").to_pylist()
    lows = table.column("low").to_pylist()
    closes = table.column("close").to_pylist()
    volumes = table.column("tick_volume").to_pylist()

    records = [
        {
            "time": t,
            "open": o,
            "high": h,
            "low": l,
            "close": c,
            "tick_volume": v,
        }
        for t, o, h, l, c, v in zip(times, opens, highs, lows, closes, volumes, strict=True)
    ]
    return CandleFrame(records)


def dataframe_to_compact_json_bytes(df: CandleFrame, limit: int | None = None) -> bytes:
    """
    Serializes candle DataFrame into compact JSON format (Array of Arrays)
    Format: [[time, open, high, low, close, volume], ...]
    """
    return df.to_compact_json_bytes(limit=limit)


def merge_rates_with_parquet(
    existing_parquet_bytes: bytes | None,
    new_rates: list[dict[str, Any]] | CandleFrame,
) -> CandleFrame:
    """
    Merges newly fetched candle rates with existing Parquet dataset,
    ensuring idempotency, deduplication, and strictly ascending timestamp ordering.
    """
    new_frame = rates_to_dataframe(new_rates)

    if not existing_parquet_bytes:
        return new_frame

    try:
        existing_frame = parquet_bytes_to_dataframe(existing_parquet_bytes)
        combined_records = existing_frame._records + new_frame._records
        return rates_to_dataframe(combined_records)
    except (Exception, BaseException) as e:
        logger.error(f"Error parsing existing Parquet bytes during merge: {e}. Using new data.")
        return new_frame
