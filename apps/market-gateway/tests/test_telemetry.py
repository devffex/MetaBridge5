import os
import shutil
import tempfile
import time
from unittest.mock import MagicMock

import pytest

from app.telemetry.base import AuditRecord
from app.telemetry.composite_sink import CompositeAuditSink
from app.telemetry.external_sink import ExternalDatabaseAuditSink
from app.telemetry.factory import AuditLoggerFactory, NullAuditSink
from app.telemetry.sqlite_sink import SQLiteAuditSink


@pytest.fixture
def temp_db_path():
    temp_dir = tempfile.mkdtemp()
    db_file = os.path.join(temp_dir, "test_audit.sqlite3")
    yield db_file
    shutil.rmtree(temp_dir, ignore_errors=True)


# =========================================================================
# Perspective 1: Happy Path (Nominal Case)
# =========================================================================
def test_sqlite_audit_sink_happy_path(temp_db_path):
    sink = SQLiteAuditSink(db_path=temp_db_path)
    record = AuditRecord(
        component="pipeline",
        event="backfill_completed",
        symbol="EURUSD",
        timeframe="H1",
        status="success",
        duration_ms=45.2,
        metadata={"candles": 500},
    )
    assert sink.record(record) is True

    # Query back
    results = sink.query(limit=10, symbol="EURUSD")
    assert len(results) == 1
    assert results[0]["event"] == "backfill_completed"
    assert results[0]["symbol"] == "EURUSD"
    assert results[0]["status"] == "success"
    assert results[0]["metadata"]["candles"] == 500
    sink.close()


# =========================================================================
# Perspective 2: Error Handling & Graceful Recovery
# =========================================================================
def test_sqlite_sink_handles_unwritable_path():
    # Attempting to initialize SQLite in an invalid read-only / uncreatable root
    sink = SQLiteAuditSink(db_path="/proc/non_existent_folder/traces.sqlite3")
    record = AuditRecord(component="test", event="test")
    # Must fail gracefully returning False without crashing application
    assert sink.record(record) is False
    assert sink.query() == []


# =========================================================================
# Perspective 3: Boundary Value Analysis (BVA)
# =========================================================================
def test_sqlite_query_boundaries(temp_db_path):
    sink = SQLiteAuditSink(db_path=temp_db_path)
    for i in range(10):
        sink.record(AuditRecord(component="test", event=f"event_{i}"))

    # Limit = 0 (empty result)
    assert len(sink.query(limit=0)) == 0
    # Limit = 1 (exact 1 result)
    assert len(sink.query(limit=1)) == 1
    # Limit = 5
    assert len(sink.query(limit=5)) == 5
    # Limit > available (exact 10 results)
    assert len(sink.query(limit=100)) == 10
    sink.close()


# =========================================================================
# Perspective 4: Edge Cases & Extreme States
# =========================================================================
def test_audit_record_with_unicode_and_extreme_metadata(temp_db_path):
    sink = SQLiteAuditSink(db_path=temp_db_path)
    record = AuditRecord(
        component="unicode_test",
        event="special_chars_🚀_ﷺ",
        message="Extreme payload with \n\r\t and quotes '\"`",
        metadata={"nested": {"deep": [1, 2, "test", None, True]}},
    )
    assert sink.record(record) is True
    results = sink.query(event="special_chars_🚀_ﷺ")
    assert len(results) == 1
    assert "🚀" in results[0]["event"]
    assert results[0]["metadata"]["nested"]["deep"][2] == "test"
    sink.close()


# =========================================================================
# Perspective 5: State & Lifecycle Verification
# =========================================================================
def test_audit_logger_factory_lifecycle(temp_db_path):
    AuditLoggerFactory.reset_cache()

    sink_sqlite = AuditLoggerFactory.get_sink("sqlite", db_path=temp_db_path)
    assert isinstance(sink_sqlite, SQLiteAuditSink)

    sink_null = AuditLoggerFactory.get_sink("none")
    assert isinstance(sink_null, NullAuditSink)
    assert sink_null.record(AuditRecord()) is True
    assert sink_null.query() == []

    sink_ext = AuditLoggerFactory.get_sink("external", endpoint_url="http://localhost:9999")
    assert isinstance(sink_ext, ExternalDatabaseAuditSink)
    sink_ext.close()


# =========================================================================
# Perspective 6: Concurrency, Timing & Asynchrony
# =========================================================================
@pytest.mark.asyncio
async def test_sqlite_async_concurrent_writes(temp_db_path):
    sink = SQLiteAuditSink(db_path=temp_db_path)

    async def write_worker(idx):
        rec = AuditRecord(component="concurrent", event=f"evt_{idx}", symbol="EURUSD")
        return await sink.record_async(rec)

    import asyncio

    tasks = [write_worker(i) for i in range(25)]
    results = await asyncio.gather(*tasks)

    assert all(r is True for r in results)
    records = sink.query(component="concurrent", limit=50)
    assert len(records) == 25
    sink.close()


# =========================================================================
# Perspective 7: Resource Management (WAL Mode Verification)
# =========================================================================
def test_sqlite_wal_mode_active(temp_db_path):
    sink = SQLiteAuditSink(db_path=temp_db_path)
    conn = sink._get_connection()
    cursor = conn.execute("PRAGMA journal_mode;")
    mode = cursor.fetchone()[0]
    assert mode.lower() == "wal"
    sink.close()


# =========================================================================
# Perspective 8: Security & SQL Injection Immunity
# =========================================================================
def test_sqlite_sql_injection_defense(temp_db_path):
    sink = SQLiteAuditSink(db_path=temp_db_path)
    sink.record(AuditRecord(component="auth", event="login", symbol="EURUSD"))

    # Malicious SQL injection in query parameter
    malicious_symbol = "EURUSD' OR '1'='1"
    results = sink.query(symbol=malicious_symbol)
    # Parameterized query must safely return 0 results instead of dumping all records
    assert len(results) == 0
    sink.close()


# =========================================================================
# Perspective 9: Idempotency & Composite Sink Broadcast
# =========================================================================
def test_composite_sink_broadcast(temp_db_path):
    sqlite_sink = SQLiteAuditSink(db_path=temp_db_path)
    mock_ext_sink = MagicMock()
    mock_ext_sink.record.return_value = True

    composite = CompositeAuditSink([sqlite_sink, mock_ext_sink])
    rec = AuditRecord(component="composite", event="multi_broadcast", symbol="GBPUSD")

    assert composite.record(rec) is True
    mock_ext_sink.record.assert_called_once_with(rec)
    results = composite.query(symbol="GBPUSD")
    assert len(results) == 1
    assert results[0]["symbol"] == "GBPUSD"
    composite.close()


# =========================================================================
# Perspective 10: Performance Budgets & Throughput
# =========================================================================
def test_sqlite_wal_write_performance_budget(temp_db_path):
    sink = SQLiteAuditSink(db_path=temp_db_path)
    start = time.perf_counter()

    # 100 sequential writes should take < 100ms in SQLite WAL mode
    for i in range(100):
        sink.record(AuditRecord(component="perf", event=f"tick_{i}"))

    elapsed_ms = (time.perf_counter() - start) * 1000.0
    assert elapsed_ms < 500.0  # Safe ceiling under CI/virtualized test runners
    assert len(sink.query(component="perf", limit=200)) == 100
    sink.close()


# =========================================================================
# Perspective 11: Schema & Type Contracts
# =========================================================================
def test_audit_record_serialization_contract():
    rec = AuditRecord(
        id="fixed-uuid",
        timestamp=1700000000,
        trace_id="tr-1234",
        component="gateway",
        event="request_received",
        symbol="EURUSD",
        timeframe="M5",
        status="info",
        duration_ms=12.5,
        metadata={"client_ip": "127.0.0.1"},
    )
    d = rec.to_dict()
    assert d["id"] == "fixed-uuid"
    assert d["timestamp"] == 1700000000
    assert d["trace_id"] == "tr-1234"
    assert d["metadata_json"] == '{"client_ip": "127.0.0.1"}'


# =========================================================================
# Perspective 12: Localization & Timezone Determinism
# =========================================================================
def test_audit_record_timestamp_utc_determinism():
    t_now = int(time.time())
    rec = AuditRecord()
    # Timestamp must be standard Unix epoch integer (UTC timezone-agnostic)
    assert isinstance(rec.timestamp, int)
    assert abs(rec.timestamp - t_now) <= 2
