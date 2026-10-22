"""
Comprehensive 12-Perspective Unit Testing Suite.
Formally maps and verifies all 12 core testing dimensions defined in .agents/skills/unit-testing/SKILL.md:
1. Happy Path
2. Error Handling & Exception Cases
3. Boundary Value Analysis (BVA)
4. Edge Cases & Extreme States
5. State & Lifecycle (FSM)
6. Concurrency, Timing & Asynchrony
7. Resource Management & Memory Cleanup
8. Security & Input Sanitization
9. Idempotency, Purity & Side-Effects
10. Performance Budgets & Complexity Bounds
11. Schema & Type System Boundaries
12. Localization & Timezone (UTC) Determinism
"""

import asyncio
import os
import time
from datetime import UTC, datetime

import pytest

from app.engine.candle0_manager import Candle0Manager
from app.pipeline.health_monitor import Severity, evaluate_tick_freshness
from app.pipeline.parquet_exporter import (
    dataframe_to_compact_json_bytes,
    dataframe_to_parquet_bytes,
    merge_rates_with_parquet,
    rates_to_dataframe,
)
from app.pipeline.stream_sink import StreamParquetSink
from app.storage.local_backend import LocalStorageBackend
from app.telemetry.base import AuditRecord
from app.telemetry.event_broadcaster import EventBroadcaster
from app.telemetry.sqlite_sink import SQLiteAuditSink


# ------------------------------------------------------------------------------
# Perspective 1: Happy Path (Nominal Case)
# ------------------------------------------------------------------------------
def test_p1_happy_path_candle0_tick_aggregation():
    manager = Candle0Manager()
    tick = {"time": 1700000000, "bid": 1.1000, "ask": 1.1002, "last": 1.1001, "volume": 10}

    asyncio.run(manager.process_tick("EURUSD", tick))
    c0 = manager.get_candle0("EURUSD", "M1")

    assert c0 is not None
    assert c0.open == 1.1001
    assert c0.high == 1.1001
    assert c0.low == 1.1001
    assert c0.close == 1.1001
    assert c0.tick_volume == 10


# ------------------------------------------------------------------------------
# Perspective 2: Error Handling & Exceptions
# ------------------------------------------------------------------------------
def test_p2_error_handling_unwritable_storage_path(tmp_path):
    unwritable = tmp_path / "read_only_dir"
    unwritable.mkdir()
    os.chmod(unwritable, 0o444)

    sink = SQLiteAuditSink(db_path=str(unwritable / "traces.sqlite3"))
    # Logging into unwritable path must fall back to memory without raising
    sink.record(AuditRecord(component="test", event="err_test", status="error"))
    traces = sink.query()
    assert isinstance(traces, list)
    sink.close()


# ------------------------------------------------------------------------------
# Perspective 3: Boundary Value Analysis (BVA)
# ------------------------------------------------------------------------------
@pytest.mark.parametrize("candle_count", [1, 500, 25000])
def test_p3_boundary_value_analysis_candle_counts(tmp_path, candle_count):
    storage = LocalStorageBackend(base_dir=str(tmp_path))
    sink = StreamParquetSink("EURUSD", "M1", storage, batch_rows=25000)

    candles = [
        {
            "time": 1700000000 + i * 60,
            "open": 1.1000,
            "high": 1.1010,
            "low": 1.0990,
            "close": 1.1005,
            "tick_volume": 1,
            "spread": 2,
            "real_volume": 0,
        }
        for i in range(candle_count)
    ]
    sink.add_candles(candles)
    summary = sink.close(write_recent_json=True)

    assert summary["records_ingested"] == candle_count
    assert summary["uploaded"] is True


# ------------------------------------------------------------------------------
# Perspective 4: Edge Cases & Extreme States
# ------------------------------------------------------------------------------
def test_p4_edge_cases_empty_and_unicode_payloads(tmp_path):
    sink = SQLiteAuditSink(db_path=str(tmp_path / "edge.sqlite3"))

    # Extreme Unicode & special characters
    record = AuditRecord(
        component="pipeline",
        event="unicode_test_🚀_ﷺ_\n\t\0",
        symbol="EUR/USD 測試",
        status="info",
        metadata={"nested_emoji": "🔥", "null_byte": "a\0b", "deep": {"k": "v"}},
    )
    sink.record(record)
    traces = sink.query()
    assert len(traces) == 1
    assert "unicode_test" in traces[0]["event"]
    sink.close()


# ------------------------------------------------------------------------------
# Perspective 5: State & Lifecycle (FSM)
# ------------------------------------------------------------------------------
def test_p5_state_transitions_stream_sink_lifecycle(tmp_path):
    storage = LocalStorageBackend(base_dir=str(tmp_path))
    sink = StreamParquetSink("USDJPY", "H1", storage)

    # Initial state: open
    assert sink._closed is False

    # Transition 1: Add row
    sink.add_candle(
        {
            "time": 1700000000,
            "open": 150.0,
            "high": 150.5,
            "low": 149.8,
            "close": 150.2,
            "tick_volume": 50,
            "spread": 1,
            "real_volume": 0,
        }
    )

    # Transition 2: Finalize/Close
    sink.close()
    assert sink._closed is True

    # Transition 3: Attempting addition on closed sink raises RuntimeError
    with pytest.raises(RuntimeError, match="Cannot add candle to a closed StreamParquetSink"):
        sink.add_candle(
            {
                "time": 1700000060,
                "open": 150.2,
                "high": 150.3,
                "low": 150.1,
                "close": 150.2,
                "tick_volume": 10,
                "spread": 1,
                "real_volume": 0,
            }
        )


# ------------------------------------------------------------------------------
# Perspective 6: Concurrency, Timing & Asynchrony
# ------------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_p6_concurrency_and_sse_pub_sub():
    eb = EventBroadcaster()
    gen1 = eb.subscribe()
    gen2 = eb.subscribe()

    # Initial connection frames
    msg1 = await anext(gen1)
    msg2 = await anext(gen2)
    assert "connected" in msg1
    assert "connected" in msg2

    # Broadcast concurrent event
    eb.broadcast("tick_stream", {"symbol": "EURUSD", "bid": 1.0850})
    event1 = await anext(gen1)
    event2 = await anext(gen2)
    assert "tick_stream" in event1
    assert "tick_stream" in event2

    await gen1.aclose()
    await gen2.aclose()


# ------------------------------------------------------------------------------
# Perspective 7: Resource Management & Cleanup
# ------------------------------------------------------------------------------
def test_p7_resource_management_sink_abort_cleanup(tmp_path):
    storage = LocalStorageBackend(base_dir=str(tmp_path))
    sink = StreamParquetSink("EURUSD", "M1", storage, batch_rows=5)

    candles = [
        {
            "time": 1700000000 + i * 60,
            "open": 1.1,
            "high": 1.2,
            "low": 1.0,
            "close": 1.15,
            "tick_volume": 10,
            "spread": 2,
            "real_volume": 0,
        }
        for i in range(12)
    ]
    sink.add_candles(candles)
    # Temporary directory was created
    temp_dir = sink._temp_dir
    assert temp_dir.exists()

    sink.abort()
    # Directory should be wiped cleanly
    assert not temp_dir.exists()


# ------------------------------------------------------------------------------
# Perspective 8: Security & Input Sanitization
# ------------------------------------------------------------------------------
def test_p8_security_sqlite_parameterization_defense(tmp_path):
    sink = SQLiteAuditSink(db_path=str(tmp_path / "sec.sqlite3"))
    sink.record(AuditRecord(component="auth", event="login", symbol="EURUSD"))

    # SQL Injection attempt in query parameters
    injected_symbol = "EURUSD' OR '1'='1"
    traces = sink.query(symbol=injected_symbol)

    # Must yield 0 results due to parameterized query matching
    assert len(traces) == 0
    sink.close()


# ------------------------------------------------------------------------------
# Perspective 9: Idempotency & Purity
# ------------------------------------------------------------------------------
def test_p9_idempotent_parquet_merges():
    raw_rates = [
        {
            "time": 1700000000,
            "open": 1.10,
            "high": 1.11,
            "low": 1.09,
            "close": 1.105,
            "tick_volume": 10,
            "spread": 1,
            "real_volume": 0,
        },
        {
            "time": 1700000060,
            "open": 1.105,
            "high": 1.12,
            "low": 1.10,
            "close": 1.115,
            "tick_volume": 15,
            "spread": 1,
            "real_volume": 0,
        },
    ]
    df1 = rates_to_dataframe(raw_rates)
    parquet_bytes = dataframe_to_parquet_bytes(df1)

    # Merge duplicate rates into the existing parquet
    merged_once = merge_rates_with_parquet(parquet_bytes, raw_rates)
    merged_twice = merge_rates_with_parquet(dataframe_to_parquet_bytes(merged_once), raw_rates)

    # Length must remain 2 (deduplicated idempotency)
    assert len(merged_once) == 2
    assert len(merged_twice) == 2


# ------------------------------------------------------------------------------
# Perspective 10: Performance Budgets & Bounds
# ------------------------------------------------------------------------------
def test_p10_performance_budget_sqlite_wal_writes(tmp_path):
    sink = SQLiteAuditSink(db_path=str(tmp_path / "perf.sqlite3"))
    start = time.perf_counter()

    # Write 100 audit records
    for i in range(100):
        sink.record(AuditRecord(component="gateway", event=f"event_{i}", symbol="EURUSD"))

    duration_sec = time.perf_counter() - start
    avg_ms = (duration_sec / 100) * 1000.0

    # Performance Budget: Average write must complete under 5ms
    assert avg_ms < 5.0
    sink.close()


# ------------------------------------------------------------------------------
# Perspective 11: Schema & Type System Boundaries
# ------------------------------------------------------------------------------
def test_p11_schema_contract_and_serialization():
    candles = [
        {
            "time": 1700000000,
            "open": 1.1000,
            "high": 1.1010,
            "low": 1.0990,
            "close": 1.1005,
            "tick_volume": 10,
            "spread": 2,
            "real_volume": 0,
        }
    ]
    df = rates_to_dataframe(candles)

    # Schema check: standard 6 columns
    expected_cols = ["time", "open", "high", "low", "close", "tick_volume"]
    assert list(df.columns) == expected_cols

    # Compact JSON Schema check: [time, open, high, low, close, tick_volume]
    compact_json = dataframe_to_compact_json_bytes(df)
    import json

    parsed = json.loads(compact_json)
    assert isinstance(parsed, list)
    assert len(parsed[0]) == 6
    assert parsed[0] == [1700000000, 1.1000, 1.1010, 1.0990, 1.1005, 10]


# ------------------------------------------------------------------------------
# Perspective 12: Localization & Timezone (UTC) Determinism
# ------------------------------------------------------------------------------
def test_p12_timezone_and_utc_determinism():
    # AuditRecord timestamp must be deterministic UTC epoch integer
    now_utc = int(datetime.now(UTC).timestamp())
    record = AuditRecord(component="test", event="utc_check")

    assert abs(record.timestamp - now_utc) <= 1
    # Check freshness evaluator with explicit UTC timestamps
    res = evaluate_tick_freshness([{"name": "EURUSD", "time": now_utc}], now_ts=now_utc)
    assert res.severity == Severity.OK
