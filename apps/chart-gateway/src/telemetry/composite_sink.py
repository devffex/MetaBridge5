import asyncio
import logging
from typing import Any

from app.telemetry.base import AuditRecord, AuditSink

logger = logging.getLogger("telemetry.composite")


class CompositeAuditSink(AuditSink):
    """
    Composite strategy sink that broadcasts audit records to multiple destinations
    (e.g., local SQLite WAL database + remote Supabase/Postgres endpoint).
    """

    def __init__(self, sinks: list[AuditSink]):
        self.sinks = sinks
        logger.info(f"Initialized CompositeAuditSink with {len(sinks)} child sinks.")

    def record(self, entry: AuditRecord) -> bool:
        success = False
        for sink in self.sinks:
            try:
                ok = sink.record(entry)
                if ok:
                    success = True
            except Exception as e:
                logger.error(f"Error in sink {type(sink).__name__}: {e}")
        return success

    async def record_async(self, entry: AuditRecord) -> bool:
        tasks = [sink.record_async(entry) for sink in self.sinks]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        return any(r is True for r in results)

    def query(
        self,
        limit: int = 100,
        symbol: str | None = None,
        event: str | None = None,
        component: str | None = None,
    ) -> list[dict[str, Any]]:
        # Query the first available queryable sink (e.g. SQLite)
        for sink in self.sinks:
            res = sink.query(limit=limit, symbol=symbol, event=event, component=component)
            if res:
                return res
        return []

    def close(self):
        for sink in self.sinks:
            try:
                sink.close()
            except Exception as e:
                logger.warning(f"Error closing sink {type(sink).__name__}: {e}")
