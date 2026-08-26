import logging
import os
from typing import ClassVar

from app.telemetry.base import AuditRecord, AuditSink
from app.telemetry.composite_sink import CompositeAuditSink
from app.telemetry.external_sink import ExternalDatabaseAuditSink
from app.telemetry.sqlite_sink import SQLiteAuditSink

logger = logging.getLogger("telemetry.factory")


class NullAuditSink(AuditSink):
    """Null sink for disabling audit logging."""

    def record(self, entry: AuditRecord) -> bool:
        return True

    async def record_async(self, entry: AuditRecord) -> bool:
        return True

    def query(
        self, limit: int = 100, symbol: str | None = None, event: str | None = None, component: str | None = None
    ):
        return []

    def close(self):
        pass


class AuditLoggerFactory:
    """
    Factory to resolve and construct the configured audit logger strategy.
    Supports SQLite WAL mode, External database endpoints, or Composite (both).
    """

    _cached_instances: ClassVar[dict[str, AuditSink]] = {}

    @classmethod
    def get_sink(cls, sink_type: str | None = None, **kwargs) -> AuditSink:
        selected = (sink_type or os.environ.get("AUDIT_LOG_SINK", "sqlite")).lower().strip()

        if selected in cls._cached_instances and not kwargs:
            return cls._cached_instances[selected]

        sink: AuditSink
        if selected == "sqlite":
            sink = SQLiteAuditSink(**kwargs)
        elif selected == "external":
            sink = ExternalDatabaseAuditSink(**kwargs)
        elif selected in ("both", "composite"):
            sqlite_sink = SQLiteAuditSink(db_path=kwargs.get("db_path", "/tmp/savisor_traces.sqlite3"))
            external_sink = ExternalDatabaseAuditSink(
                endpoint_url=kwargs.get("endpoint_url"),
                api_key=kwargs.get("api_key"),
            )
            sink = CompositeAuditSink([sqlite_sink, external_sink])
        elif selected in ("none", "off", "disabled"):
            sink = NullAuditSink()
        else:
            logger.warning(f"Unknown AUDIT_LOG_SINK '{selected}', defaulting to SQLite.")
            sink = SQLiteAuditSink(**kwargs)

        if not kwargs:
            cls._cached_instances[selected] = sink

        return sink

    @classmethod
    def reset_cache(cls):
        cls._cached_instances.clear()
