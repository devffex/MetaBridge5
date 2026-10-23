"""
StreamParquetSink - Staged In-Memory & Parquet Chunk Sink for Market Ingestion.
Adopted from the enterprise streaming sink patterns in cifra-connectors.
"""

from __future__ import annotations

import contextlib
import logging
import os
import tempfile
import time
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq

from app.pipeline.parquet_exporter import rates_to_dataframe
from app.storage.base import StorageBackend

logger = logging.getLogger(__name__)

DEFAULT_PARQUET_BATCH_ROWS = 25_000


def parquet_batch_rows() -> int:
    raw_val = os.getenv("METABRIDGE5_PARQUET_BATCH_ROWS")
    if not raw_val:
        return DEFAULT_PARQUET_BATCH_ROWS
    try:
        return max(100, int(raw_val))
    except ValueError:
        return DEFAULT_PARQUET_BATCH_ROWS


class StreamParquetSink:
    """
    Manages in-memory buffering, temporary staged local Parquet chunks,
    and atomic publishing to the configured StorageBackend with safe abort() rollbacks.
    """

    def __init__(
        self,
        symbol: str,
        timeframe: str,
        storage_backend: StorageBackend,
        batch_rows: int | None = None,
    ):
        self.symbol = symbol.upper()
        self.timeframe = timeframe.upper()
        self.storage = storage_backend
        self.batch_rows = max(100, batch_rows or parquet_batch_rows())
        self._buffer: list[dict[str, Any]] = []
        self._all_rows: list[dict[str, Any]] = []
        self._temp_dir = Path(tempfile.mkdtemp(prefix=f"metabridge5_sink_{self.symbol}_{self.timeframe}_"))
        self._chunk_paths: list[Path] = []
        self._closed = False
        self._start_time = time.time()
        self._chunks_flushed = 0

    def add_candle(self, candle: dict[str, Any]) -> None:
        """Appends a candle to the active stream buffer, flushing when batch size is reached."""
        if self._closed:
            raise RuntimeError("Cannot add candle to a closed StreamParquetSink")
        self._buffer.append(candle)
        self._all_rows.append(candle)

        if len(self._buffer) >= self.batch_rows:
            self._flush_chunk()

    def add_candles(self, candles: Sequence[dict[str, Any]]) -> None:
        """Appends a batch of candles to the stream buffer."""
        for c in candles:
            self.add_candle(c)

    def _flush_chunk(self) -> None:
        """Writes current in-memory buffer to a local temporary Parquet chunk with Snappy compression."""
        if not self._buffer:
            return
        chunk_idx = len(self._chunk_paths)
        chunk_path = self._temp_dir / f"chunk_{chunk_idx:04d}.parquet"

        df = rates_to_dataframe(self._buffer)
        table = pa.Table.from_pandas(df, preserve_index=False)

        pq.write_table(table, chunk_path, compression="snappy")
        self._chunk_paths.append(chunk_path)
        self._chunks_flushed += 1
        self._buffer.clear()
        logger.debug(f"Flushed chunk {chunk_idx} for {self.symbol} {self.timeframe} ({len(df)} rows)")

    def close(self, write_recent_json: bool = True) -> dict[str, Any]:
        """
        Finalizes all pending buffers, merges/appends to existing dataset,
        and atomically uploads to the storage backend.
        Returns a structured execution summary.
        """
        if self._closed:
            raise RuntimeError("StreamParquetSink.close() can only be called once")
        self._closed = True

        # Flush any remaining rows
        if self._buffer:
            self._flush_chunk()

        total_records = len(self._all_rows)
        parquet_key = f"{self.symbol}/{self.timeframe}/history.parquet"
        json_key = f"{self.symbol}/{self.timeframe}/recent.json"

        if total_records == 0:
            self._cleanup_temp()
            return {
                "symbol": self.symbol,
                "timeframe": self.timeframe,
                "records_ingested": 0,
                "chunks_flushed": 0,
                "uploaded": False,
                "skip_reason": "zero_records",
                "duration_ms": round((time.time() - self._start_time) * 1000.0, 2),
            }

        try:
            from app.pipeline.parquet_exporter import (
                dataframe_to_compact_json_bytes,
                dataframe_to_parquet_bytes,
                merge_rates_with_parquet,
            )

            # Read existing Parquet data from storage if available
            existing_bytes = self.storage.read_bytes(parquet_key)
            merged_df = merge_rates_with_parquet(existing_bytes, self._all_rows)

            new_parquet_bytes = dataframe_to_parquet_bytes(merged_df)
            self.storage.upload_bytes(new_parquet_bytes, parquet_key, content_type="application/vnd.apache.parquet")

            if write_recent_json:
                new_json_bytes = dataframe_to_compact_json_bytes(merged_df, limit=500)
                self.storage.upload_bytes(new_json_bytes, json_key, content_type="application/json")

            duration_ms = round((time.time() - self._start_time) * 1000.0, 2)
            logger.info(
                f"StreamParquetSink successfully committed {total_records} rows for {self.symbol} {self.timeframe} in {duration_ms}ms"
            )

            return {
                "symbol": self.symbol,
                "timeframe": self.timeframe,
                "records_ingested": total_records,
                "total_partition_rows": len(merged_df),
                "chunks_flushed": self._chunks_flushed,
                "parquet_key": parquet_key,
                "json_key": json_key if write_recent_json else None,
                "uploaded": True,
                "duration_ms": duration_ms,
            }
        finally:
            self._cleanup_temp()

    def abort(self) -> None:
        """Cancels writing and wipes temporary files safely upon errors."""
        self._closed = True
        self._buffer.clear()
        self._all_rows.clear()
        self._cleanup_temp()
        logger.warning(f"StreamParquetSink aborted and cleaned up for {self.symbol} {self.timeframe}")

    def _cleanup_temp(self) -> None:
        """Removes local temporary chunk files and directory."""
        for p in self._chunk_paths:
            with contextlib.suppress(Exception):
                p.unlink(missing_ok=True)
        with contextlib.suppress(Exception):
            self._temp_dir.rmdir()
