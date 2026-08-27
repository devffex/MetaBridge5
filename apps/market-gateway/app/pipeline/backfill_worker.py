"""
BackfillWorker - Orchestrates deep historical ingestion, incremental candle rollups,
and granular per-symbol / exclusionary pipeline ingestion controls.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Any

from app.grpc_client import TerminalGRPCClient
from app.pipeline.stream_sink import StreamParquetSink
from app.storage.base import StorageBackend
from app.telemetry.base import AuditRecord, AuditSink
from app.telemetry.event_broadcaster import broadcaster

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

        # Granular & Global Ingestion Pause Control States
        self.global_paused: bool = False
        self._paused_symbols: set[str] = set()

        logger.info(f"Initialized BackfillWorker with storage: {type(storage_backend).__name__}")

    @property
    def is_paused(self) -> bool:
        """Backward-compatible boolean indicating if the entire pipeline is globally paused."""
        return self.global_paused

    def is_symbol_paused(self, symbol: str) -> bool:
        """Returns True if the symbol is individually paused or if global pipeline is paused."""
        sym = symbol.upper()
        return self.global_paused or (sym in self._paused_symbols)

    def get_paused_symbols(self) -> list[str]:
        """Returns a sorted list of individually paused symbols."""
        return sorted(self._paused_symbols)

    def pause(self, symbol: str | None = None) -> dict[str, Any]:
        """Pauses historical data extraction and storage pushes globally or for a specific symbol."""
        if symbol:
            sym = symbol.upper()
            self._paused_symbols.add(sym)
            logger.warning(f"Pipeline ingestion PAUSED for symbol: {sym}")
            broadcaster.broadcast("pipeline_paused", {"symbol": sym, "scope": "symbol"})
            return {
                "status": "paused",
                "scope": "symbol",
                "symbol": sym,
                "paused_symbols": self.get_paused_symbols(),
                "global_paused": self.global_paused,
            }

        self.global_paused = True
        logger.warning("Pipeline ingestion and storage pushes GLOBALLY PAUSED")
        broadcaster.broadcast("pipeline_paused", {"scope": "global"})
        return {
            "status": "paused",
            "scope": "global",
            "global_paused": True,
            "paused_symbols": self.get_paused_symbols(),
        }

    def resume(self, symbol: str | None = None) -> dict[str, Any]:
        """Resumes historical data extraction and storage pushes globally or for a specific symbol."""
        if symbol:
            sym = symbol.upper()
            self._paused_symbols.discard(sym)
            logger.info(f"Pipeline ingestion RESUMED for symbol: {sym}")
            broadcaster.broadcast("pipeline_resumed", {"symbol": sym, "scope": "symbol"})
            return {
                "status": "active",
                "scope": "symbol",
                "symbol": sym,
                "paused_symbols": self.get_paused_symbols(),
                "global_paused": self.global_paused,
            }

        self.global_paused = False
        self._paused_symbols.clear()
        logger.info("Pipeline ingestion and storage pushes GLOBALLY RESUMED (all symbols unpaused)")
        broadcaster.broadcast("pipeline_resumed", {"scope": "global"})
        return {
            "status": "active",
            "scope": "global",
            "global_paused": False,
            "paused_symbols": [],
        }

    def bulk_control(
        self,
        action: str,
        scope: str,
        symbols: list[str] | None = None,
        active_symbols: list[str] | None = None,
    ) -> dict[str, Any]:
        """
        Executes granular or exclusionary bulk pause/resume operations across symbols.
        - scope: 'all' -> pause/resume everything.
        - scope: 'symbols' -> pause/resume specified symbols.
        - scope: 'exclude' -> pause all active symbols except specified symbols (e.g. ingest ONLY USDJPY).
        """
        action = action.lower()
        scope = scope.lower()
        targets = [s.upper() for s in (symbols or [])]
        active = [s.upper() for s in (active_symbols or [])]

        if scope == "all":
            if action == "pause":
                return self.pause()
            return self.resume()

        if scope == "symbols":
            for s in targets:
                if action == "pause":
                    self._paused_symbols.add(s)
                else:
                    self._paused_symbols.discard(s)
            broadcaster.broadcast(f"pipeline_{action}", {"scope": "symbols", "symbols": targets})
            return {
                "status": "success",
                "action": action,
                "scope": "symbols",
                "affected_symbols": targets,
                "paused_symbols": self.get_paused_symbols(),
                "global_paused": self.global_paused,
            }

        if scope == "exclude":
            # Target symbols remain ACTIVE; all other active symbols are PAUSED
            self.global_paused = False
            self._paused_symbols.clear()
            for s in active:
                if s not in targets:
                    self._paused_symbols.add(s)
            logger.info(
                f"Bulk control applied exclusion: Ingesting ONLY {targets}, paused: {self.get_paused_symbols()}"
            )
            broadcaster.broadcast(
                "pipeline_exclusion_applied", {"active_only": targets, "paused": self.get_paused_symbols()}
            )
            return {
                "status": "success",
                "action": "exclusive_ingest",
                "scope": "exclude",
                "active_only": targets,
                "paused_symbols": self.get_paused_symbols(),
                "global_paused": False,
            }

        raise ValueError(f"Invalid scope '{scope}'. Supported scopes: 'all', 'symbols', 'exclude'")

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

        if self.is_symbol_paused(symbol):
            logger.warning(f"Pipeline is paused for {symbol}. Skipping backfill.")
            return {
                "symbol": symbol,
                "status": "paused",
                "message": f"Pipeline ingestion is paused for {symbol}. Resume to execute backfill.",
                "timeframes": tfs,
            }

        lock = await self._get_symbol_lock(symbol)
        start_time_sec = time.time()

        broadcaster.broadcast(
            "backfill_started",
            {"symbol": symbol, "timeframes": tfs, "candle_count": candle_count},
        )

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
            "start_time": int(start_time_sec),
            "updated_at": int(start_time_sec),
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

                    sink = StreamParquetSink(symbol, tf, self.storage)
                    all_rates: list[dict[str, Any]] = []

                    if date_from and date_to:
                        logger.info(f"Backfilling {symbol} {tf} date range {date_from} -> {date_to}...")
                        all_rates = await asyncio.to_thread(
                            self.grpc_client.get_rates_range, symbol, tf_val, date_from, date_to
                        )
                    else:
                        chunk_size = 25000
                        logger.info(
                            f"Backfilling {symbol} {tf} (target_count={candle_count}, chunk_size={chunk_size})..."
                        )
                        start_pos = 0
                        remaining = candle_count

                        while remaining > 0:
                            current_batch_size = min(remaining, chunk_size)
                            batch = await asyncio.to_thread(
                                self.grpc_client.get_rates_from_pos, symbol, tf_val, start_pos, current_batch_size
                            )
                            if not batch:
                                logger.info(
                                    f"No further historical rates returned for {symbol} {tf} at pos {start_pos}"
                                )
                                break

                            all_rates.extend(batch)
                            start_pos += len(batch)
                            remaining -= len(batch)

                            broadcaster.broadcast(
                                "backfill_chunk_fetched",
                                {
                                    "symbol": symbol,
                                    "timeframe": tf,
                                    "chunk_rows": len(batch),
                                    "total_fetched": len(all_rates),
                                },
                            )

                            if len(batch) < current_batch_size:
                                break

                    if not all_rates:
                        logger.warning(f"No rates returned for {symbol} {tf}")
                        sink.abort()
                        results["timeframes"][tf] = {"count": 0, "status": "empty"}
                        continue

                    sink.add_candles(all_rates)
                    sink_summary = sink.close(write_recent_json=True)

                    results["timeframes"][tf] = {
                        "candle_count": sink_summary.get("total_partition_rows", len(all_rates)),
                        "records_ingested": sink_summary.get("records_ingested", len(all_rates)),
                        "chunks_flushed": sink_summary.get("chunks_flushed", 1),
                        "parquet_uploaded": sink_summary.get("uploaded", True),
                        "json_uploaded": sink_summary.get("uploaded", True),
                        "parquet_url": self.storage.get_public_url(f"data/{symbol}/{tf}/history.parquet"),
                        "json_url": self.storage.get_public_url(f"data/{symbol}/{tf}/recent.json"),
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

                broadcaster.broadcast("backfill_completed", {"symbol": symbol, "duration_ms": elapsed_ms})

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

                broadcaster.broadcast("backfill_failed", {"symbol": symbol, "error": str(e)})

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

        if self.is_symbol_paused(symbol):
            logger.debug(f"Pipeline is currently paused for {symbol}. Skipping closed candle rollup.")
            return

        lock = await self._get_symbol_lock(symbol)
        start_time_sec = time.time()

        async with lock:
            try:
                logger.info(
                    f"Incrementally rolling closed candle for {symbol} {timeframe} at {closed_candle.get('time')}"
                )
                sink = StreamParquetSink(symbol, timeframe, self.storage)
                sink.add_candle(closed_candle)
                sink.close(write_recent_json=True)

                elapsed_ms = (time.time() - start_time_sec) * 1000.0
                logger.debug(f"Incremental rollup saved for {symbol} {timeframe} ({elapsed_ms:.2f}ms)")

                broadcaster.broadcast(
                    "candle_closed_rollup",
                    {
                        "symbol": symbol,
                        "timeframe": timeframe,
                        "candle_time": closed_candle.get("time"),
                        "close": closed_candle.get("close"),
                        "duration_ms": elapsed_ms,
                    },
                )

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
