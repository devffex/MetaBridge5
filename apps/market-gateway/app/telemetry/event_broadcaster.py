"""
Real-Time Event Broadcaster for Server-Sent Events (SSE) Telemetry.
Allows operators and dashboards to tail live pipeline and candle events.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from collections.abc import AsyncGenerator
from typing import Any

logger = logging.getLogger(__name__)


class EventBroadcaster:
    """Thread-safe async publish/subscribe broadcaster for real-time pipeline telemetry."""

    def __init__(self, max_queue_size: int = 100):
        self._listeners: set[asyncio.Queue] = set()
        self._max_queue_size = max_queue_size

    def broadcast(self, event_type: str, data: dict[str, Any] | None = None) -> None:
        """Broadcasts an event payload to all currently connected SSE listeners."""
        payload = {
            "timestamp": int(time.time()),
            "event": event_type,
            **(data or {}),
        }
        dead_listeners = set()
        for q in list(self._listeners):
            try:
                if q.full():
                    # Drop oldest event if full to prevent blocking
                    try:
                        q.get_nowait()
                    except asyncio.QueueEmpty:
                        pass
                q.put_nowait(payload)
            except Exception:
                dead_listeners.add(q)

        for dead in dead_listeners:
            self._listeners.discard(dead)

    async def subscribe(self) -> AsyncGenerator[str, None]:
        """Subscribes a client and yields formatted Server-Sent Events (SSE)."""
        queue: asyncio.Queue = asyncio.Queue(maxsize=self._max_queue_size)
        self._listeners.add(queue)
        # Yield initial connection heartbeat
        yield f"data: {json.dumps({'event': 'connected', 'timestamp': int(time.time()), 'message': 'SSE telemetry stream established'})}\n\n"

        try:
            while True:
                try:
                    payload = await asyncio.wait_for(queue.get(), timeout=15.0)
                    yield f"data: {json.dumps(payload)}\n\n"
                except TimeoutError:
                    # Send periodic keep-alive comment
                    yield ": keep-alive\n\n"
        finally:
            self._listeners.discard(queue)


# Singleton event broadcaster instance
broadcaster = EventBroadcaster()
