import asyncio
import logging
import os
from typing import Any

import httpx

from app.telemetry.base import AuditRecord, AuditSink

logger = logging.getLogger("telemetry.external")


class ExternalDatabaseAuditSink(AuditSink):
    """
    External Database / Telemetry sink (Supabase, PostgreSQL PostgREST, Loki, ClickHouse).
    Uses asynchronous buffered queue dispatch to decouple remote network latency from local loops.
    """

    def __init__(
        self,
        endpoint_url: str | None = None,
        api_key: str | None = None,
        buffer_size: int = 50,
        flush_interval_sec: float = 2.0,
    ):
        self.endpoint_url = endpoint_url or os.environ.get("AUDIT_EXTERNAL_ENDPOINT")
        self.api_key = api_key or os.environ.get("AUDIT_EXTERNAL_API_KEY")
        self.buffer_size = buffer_size
        self.flush_interval = flush_interval_sec
        self._queue: asyncio.Queue = asyncio.Queue(maxsize=1000)
        self._worker_task: asyncio.Task | None = None
        self._is_running = True
        self._headers = {"Content-Type": "application/json"}
        if self.api_key:
            self._headers["Authorization"] = f"Bearer {self.api_key}"
            self._headers["apikey"] = self.api_key

        logger.info(f"Initialized ExternalDatabaseAuditSink (Endpoint: {self.endpoint_url})")

    def _ensure_worker(self):
        if self._worker_task is None or self._worker_task.done():
            try:
                loop = asyncio.get_running_loop()
                self._worker_task = loop.create_task(self._flush_loop())
            except RuntimeError:
                pass

    async def _flush_loop(self):
        while self._is_running:
            batch: list[AuditRecord] = []
            try:
                # Wait for at least one item
                first = await asyncio.wait_for(self._queue.get(), timeout=self.flush_interval)
                batch.append(first)
                self._queue.task_done()

                # Drain available items up to buffer_size
                while len(batch) < self.buffer_size and not self._queue.empty():
                    item = self._queue.get_nowait()
                    batch.append(item)
                    self._queue.task_done()
            except TimeoutError:
                pass
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in external audit queue drain: {e}")

            if batch and self.endpoint_url:
                await self._send_batch(batch)

    async def _send_batch(self, batch: list[AuditRecord]):
        payload = [entry.to_dict() for entry in batch]
        for attempt in range(3):
            try:
                async with httpx.AsyncClient(timeout=5.0) as client:
                    res = await client.post(self.endpoint_url, headers=self._headers, json=payload)
                    if res.status_code in (200, 201, 204):
                        logger.debug(f"Shipped {len(batch)} audit records to external database.")
                        return
                    else:
                        logger.warning(f"External audit ship returned status {res.status_code}: {res.text}")
            except Exception as e:
                logger.error(f"Error sending audit batch to external sink (attempt {attempt + 1}/3): {e}")
                await asyncio.sleep(0.5 * (2**attempt))

    def record(self, entry: AuditRecord) -> bool:
        self._ensure_worker()
        try:
            self._queue.put_nowait(entry)
            return True
        except asyncio.QueueFull:
            logger.warning("External audit queue full, dropping oldest record.")
            return False
        except Exception as e:
            logger.error(f"Failed to queue external audit record: {e}")
            return False

    async def record_async(self, entry: AuditRecord) -> bool:
        return self.record(entry)

    def query(
        self,
        limit: int = 100,
        symbol: str | None = None,
        event: str | None = None,
        component: str | None = None,
    ) -> list[dict[str, Any]]:
        # External query requires query API on remote endpoint
        return []

    def close(self):
        self._is_running = False
        if self._worker_task:
            self._worker_task.cancel()
