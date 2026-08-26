import asyncio
import json
import logging
import time
from typing import Any

from app.grpc_client import TerminalGRPCClient
from app.pipeline.parquet_exporter import (
    dataframe_to_compact_json_bytes,
    dataframe_to_parquet_bytes,
    merge_rates_with_parquet,
)
from app.storage.base import StorageBackend
from app.telemetry.base import AuditRecord, AuditSink

logger = logging.getLogger("pipeline.backfill_worker")

# Timeframe mapping to MT5 integer constants
TIMEFRAME_MAP = {
    "M1": 1,
    "M2": 2,
    "M3": 3,
    "M4": 4,
    "M5": 5,
    "M6": 6,
    "M10": 10,
    "M12": 12,
    "M15": 15,
    "M20": 20,
    "M30": 30,
    "H1": 16385,
    "H2": 16386,
    "H3": 16387,
    "H4": 16388,
    "H6": 16390,
    "H8": 16392,
    "H12": 16396,
    "D1": 16408,
    "W1": 32769,
    "MN1": 49153,
}


class BackfillWorker:
    """
    Orchestrates historical data backfilling and incremental dataset rollups.
    Interacts with MT5 gRPC client, parses candles into Parquet/JSON,
    and publishes to the active StorageBackend.
    """

    def __init__(
        self,
        grpc_client: TerminalGRPCClient,
        storage_backend: StorageBackend,
        audit_sink: AuditSink | None = None,
        default_timeframes: list[str] | None = None,
    ):
        self.grpc_client = grpc_client
        self.storage = storage_backend
        self.audit_sink = audit_sink
        self.timeframes = default_timeframes or ["M1", "M5", "M15", "M30", "H1", "H4", "D1"]
        # Symbol sync locks to avoid concurrent writes to the same dataset partition
        self._sync_locks: dict[str, asyncio.Lock] = {}
        self._master_lock = asyncio.Lock()
        self.status_registry: dict[str, Any] = {}
        logger.info(f"Initialized BackfillWorker with storage: {type(storage_backend).__name__}")

    async def _get_symbol_lock(self, symbol: str) -> asyncio.Lock:
        async with self._master_lock:
            if symbol not in self._sync_locks:
                self._sync_locks[symbol] = asyncio.Lock()
            return self._sync_locks[symbol]

    async def run_initial_backfill(
        self,
        symbol: str,
        timeframes: list[str] | None = None,
        candle_count: int = 10000,
        date_from: str | None = None,
        date_to: str | None = None,
    ) -> dict[str, Any]:
        """
        Executes a deep historical backfill for the specified symbol across timeframes.
        Supports batch chunking for large candle counts (>25,000) and ISO 8601 date ranges.
        Writes Parquet history and recent.json partitions to the storage backend.
        """
        symbol = symbol.upper()
        tfs = timeframes or self.timeframes
        lock = await self._get_symbol_lock(symbol)
        start_time_sec = time.time()

        if self.audit_sink:
            self.audit_sink.record(
                AuditRecord(
                    component="pipeline",
                    event="backfill_started",
                    symbol=symbol,
                    status="info",
                    metadata={
                        "timeframes": tfs,
                        "candle_count": candle_count,
                        "date_from": date_from,
                        "date_to": date_to,
                    },
                )
            )

        results: dict[str, Any] = {
            "symbol": symbol,
            "timeframes": {},
            "status": "in_progress",
            "started_at": int(start_time_sec),
        }
        self.status_registry[symbol] = results

        async with lock:
            try:
                # Ensure symbol is active in terminal Market Watch
                await asyncio.to_thread(self.grpc_client.select_symbol, symbol, True)

                for tf in tfs:
                    tf_val = TIMEFRAME_MAP.get(tf.upper())
                    if not tf_val:
                        logger.warning(f"Skipping unsupported timeframe: {tf}")
                        continue

                    all_rates: list[dict[str, Any]] = []

                    if date_from and date_to:
                        logger.info(f"Backfilling {symbol} {tf} date range {date_from} -> {date_to}...")
                        all_rates = await asyncio.to_thread(
                            self.grpc_client.get_rates_range, symbol, tf_val, date_from, date_to
                        )
                    else:
                        # Chunked batch pagination for large candle counts
                        chunk_size = 25000
                        logger.info(f"Backfilling {symbol} {tf} (target_count={candle_count}, chunk_size={chunk_size})...")
                        start_pos = 0
                        remaining = candle_count

                        while remaining > 0:
                            current_batch_size = min(remaining, chunk_size)
                            batch = await asyncio.to_thread(
                                self.grpc_client.get_rates_from_pos, symbol, tf_val, start_pos, current_batch_size
                            )
                            if not batch:
                                logger.info(f"No further historical rates returned for {symbol} {tf} at pos {start_pos}")
                                break

                            all_rates.extend(batch)
                            start_pos += len(batch)
                            remaining -= len(batch)

                            # If batch returned fewer than requested, terminal reached oldest available history
                            if len(batch) < current_batch_size:
                                break

                    if not all_rates:
                        logger.warning(f"No rates returned for {symbol} {tf}")
                        results["timeframes"][tf] = {"count": 0, "status": "empty"}
                        continue

                    parquet_path = f"data/{symbol}/{tf}/history.parquet"
                    json_path = f"data/{symbol}/{tf}/recent.json"

                    existing_bytes = self.storage.read_bytes(parquet_path)
                    merged_df = merge_rates_with_parquet(existing_bytes, all_rates)

                    parquet_bytes = dataframe_to_parquet_bytes(merged_df)
                    recent_json_bytes = dataframe_to_compact_json_bytes(merged_df, limit=500)

                    p_ok = self.storage.upload_bytes(
                        parquet_bytes, parquet_path, content_type="application/vnd.apache.parquet"
                    )
                    j_ok = self.storage.upload_bytes(recent_json_bytes, json_path, content_type="application/json")

                    results["timeframes"][tf] = {
                        "candle_count": len(merged_df),
                        "start_time": int(merged_df["time"].min()),
                        "end_time": int(merged_df["time"].max()),
                        "parquet_uploaded": p_ok,
                        "json_uploaded": j_ok,
                        "parquet_url": self.storage.get_public_url(parquet_path),
                        "json_url": self.storage.get_public_url(json_path),
                    }

                manifest_path = f"data/{symbol}/manifest.json"
                manifest_data = {
                    "symbol": symbol,
                    "last_updated": int(time.time()),
                    "timeframes": results["timeframes"],
                }
                self.storage.upload_bytes(
                    json.dumps(manifest_data, indent=2).encode("utf-8"),
                    manifest_path,
                    content_type="application/json",
                )

                elapsed_ms = (time.time() - start_time_sec) * 1000.0
                results["status"] = "completed"

                results["completed_at"] = int(time.time())
                results["duration_ms"] = round(elapsed_ms, 2)
                logger.info(f"Successfully completed deep backfill for {symbol} in {elapsed_ms:.2f}ms")

                if self.audit_sink:
                    self.audit_sink.record(
                        AuditRecord(
                            component="pipeline",
                            event="backfill_completed",
                            symbol=symbol,
                            status="success",
                            duration_ms=elapsed_ms,
                            metadata={"timeframes_synced": list(results["timeframes"].keys())},
                        )
                    )

                return results

            except Exception as e:
                logger.exception(f"Backfill failed for {symbol}")
                elapsed_ms = (time.time() - start_time_sec) * 1000.0
                results["status"] = "failed"
                results["error"] = str(e)
                results["duration_ms"] = round(elapsed_ms, 2)

                if self.audit_sink:
                    self.audit_sink.record(
                        AuditRecord(
                            component="pipeline",
                            event="backfill_failed",
                            symbol=symbol,
                            status="error",
                            duration_ms=elapsed_ms,
                            message=str(e),
                        )
                    )

                return results

    async def handle_candle_close(self, symbol: str, timeframe: str, closed_candle: dict[str, Any]):
        """
        Incremental sync invoked by Candle0Manager when a candle period closes.
        Appends closed candle to the recent.json and history.parquet datasets.
        """
        symbol = symbol.upper()
        timeframe = timeframe.upper()
        lock = await self._get_symbol_lock(symbol)
        start_time_sec = time.time()

        async with lock:
            try:
                logger.info(
                    f"Incrementally rolling closed candle for {symbol} {timeframe} at {closed_candle.get('time')}"
                )
                parquet_path = f"data/{symbol}/{timeframe}/history.parquet"
                json_path = f"data/{symbol}/{timeframe}/recent.json"

                existing_bytes = self.storage.read_bytes(parquet_path)
                merged_df = merge_rates_with_parquet(existing_bytes, [closed_candle])

                new_parquet_bytes = dataframe_to_parquet_bytes(merged_df)
                new_json_bytes = dataframe_to_compact_json_bytes(merged_df, limit=500)

                self.storage.upload_bytes(
                    new_parquet_bytes, parquet_path, content_type="application/vnd.apache.parquet"
                )
                self.storage.upload_bytes(new_json_bytes, json_path, content_type="application/json")
                elapsed_ms = (time.time() - start_time_sec) * 1000.0
                logger.debug(f"Incremental rollup saved for {symbol} {timeframe} ({elapsed_ms:.2f}ms)")

                if self.audit_sink:
                    self.audit_sink.record(
                        AuditRecord(
                            component="pipeline",
                            event="candle_closed_rollup",
                            symbol=symbol,
                            timeframe=timeframe,
                            status="success",
                            duration_ms=elapsed_ms,
                            metadata={"candle_time": closed_candle.get("time"), "close": closed_candle.get("close")},
                        )
                    )
            except Exception as e:
                logger.error(f"Failed incremental rollup for {symbol} {timeframe}: {e}")
                if self.audit_sink:
                    self.audit_sink.record(
                        AuditRecord(
                            component="pipeline",
                            event="candle_rollup_failed",
                            symbol=symbol,
                            timeframe=timeframe,
                            status="error",
                            message=str(e),
                        )
                    )
