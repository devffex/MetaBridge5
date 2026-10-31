import asyncio
import json
import logging
import os
import sqlite3
import threading
from pathlib import Path
from typing import Any

from app.telemetry.base import AuditRecord, AuditSink

logger = logging.getLogger("telemetry.sqlite")


class SQLiteAuditSink(AuditSink):
    """
    Internal SQLite audit and trace logger with Write-Ahead Logging (WAL) mode.
    Provides ultra-fast, local, zero-overhead storage for pipeline operations.
    """

    def __init__(self, db_path: str | None = None):
        if db_path is None:
            data_dir = os.environ.get("METABRIDGE5_DATA_DIR")
            if data_dir:
                db_path = str(Path(data_dir) / "metabridge5_traces.sqlite3")
            else:
                db_path = "/tmp/metabridge5_traces.sqlite3"
        self.db_path = Path(db_path)
        self._local = threading.local()
        self._lock = threading.Lock()
        self._is_ready = False
        try:
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            self._init_db()
            self._is_ready = True
            logger.info(f"Initialized SQLiteAuditSink (WAL mode) at {self.db_path}")
        except Exception as e:
            logger.error(f"Failed to initialize SQLiteAuditSink at {self.db_path}: {e}")

    def _get_connection(self) -> sqlite3.Connection | None:
        if not self._is_ready:
            return None
        if not hasattr(self._local, "conn") or self._local.conn is None:
            conn = sqlite3.connect(str(self.db_path), timeout=10.0, check_same_thread=False)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("PRAGMA synchronous=NORMAL;")
            self._local.conn = conn
        return self._local.conn

    def _init_db(self):
        with self._lock:
            conn = sqlite3.connect(str(self.db_path), timeout=10.0)
            try:
                conn.execute("PRAGMA journal_mode=WAL;")
                conn.execute("PRAGMA synchronous=NORMAL;")
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS audit_traces (
                        id TEXT PRIMARY KEY,
                        timestamp INTEGER NOT NULL,
                        trace_id TEXT NOT NULL,
                        component TEXT NOT NULL,
                        event TEXT NOT NULL,
                        symbol TEXT,
                        timeframe TEXT,
                        status TEXT NOT NULL,
                        duration_ms REAL,
                        message TEXT,
                        metadata_json TEXT
                    );
                """)
                conn.execute("CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON audit_traces(timestamp DESC);")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_audit_trace_id ON audit_traces(trace_id);")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_audit_sym_evt ON audit_traces(symbol, event);")
                conn.commit()
            finally:
                conn.close()

    def record(self, entry: AuditRecord) -> bool:
        try:
            conn = self._get_connection()
            if conn is None:
                return False
            metadata_str = json.dumps(entry.metadata) if entry.metadata else "{}"
            conn.execute(
                """
                INSERT INTO audit_traces (
                    id, timestamp, trace_id, component, event, symbol,
                    timeframe, status, duration_ms, message, metadata_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    entry.id,
                    entry.timestamp,
                    entry.trace_id,
                    entry.component,
                    entry.event,
                    entry.symbol,
                    entry.timeframe,
                    entry.status,
                    entry.duration_ms,
                    entry.message,
                    metadata_str,
                ),
            )
            conn.commit()
            return True
        except Exception as e:
            logger.error(f"Failed to record audit entry in SQLite: {e}")
            return False

    async def record_async(self, entry: AuditRecord) -> bool:
        return await asyncio.to_thread(self.record, entry)

    def query(
        self,
        limit: int = 100,
        symbol: str | None = None,
        event: str | None = None,
        component: str | None = None,
    ) -> list[dict[str, Any]]:
        try:
            conn = self._get_connection()
            if conn is None:
                return []
            clauses = []
            params = []

            if symbol:
                clauses.append("symbol = ?")
                params.append(symbol.upper())
            if event:
                clauses.append("event = ?")
                params.append(event)
            if component:
                clauses.append("component = ?")
                params.append(component)

            where_sql = ("WHERE " + " AND ".join(clauses)) if clauses else ""
            sql = f"SELECT * FROM audit_traces {where_sql} ORDER BY timestamp DESC LIMIT ?"
            params.append(limit)

            cursor = conn.execute(sql, params)
            rows = cursor.fetchall()
            results = []
            for r in rows:
                d = dict(r)
                if d.get("metadata_json"):
                    try:
                        d["metadata"] = json.loads(d["metadata_json"])
                    except Exception:
                        d["metadata"] = {}
                results.append(d)
            return results
        except Exception as e:
            logger.error(f"Failed to query audit traces from SQLite: {e}")
            return []

    def close(self):
        if hasattr(self._local, "conn") and self._local.conn is not None:
            try:
                self._local.conn.close()
            except Exception as e:
                logger.warning(f"Error closing SQLite connection: {e}")
            self._local.conn = None
