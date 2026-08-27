import json
import time
import uuid
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class AuditRecord:
    """
    Standardized schema for audit logs, distributed traces, and pipeline telemetry events.
    """

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: int = field(default_factory=lambda: int(time.time()))
    trace_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    component: str = "general"
    event: str = "event"
    symbol: str | None = None
    timeframe: str | None = None
    status: str = "info"  # "info", "success", "warning", "error"
    duration_ms: float | None = None
    message: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["metadata_json"] = json.dumps(self.metadata)
        return d


class AuditSink(ABC):
    """
    Abstract Strategy Interface for persisting audit and trace logs.
    """

    @abstractmethod
    def record(self, entry: AuditRecord) -> bool:
        """Synchronously records an audit record."""

    @abstractmethod
    async def record_async(self, entry: AuditRecord) -> bool:
        """Asynchronously records an audit record."""

    @abstractmethod
    def query(
        self,
        limit: int = 100,
        symbol: str | None = None,
        event: str | None = None,
        component: str | None = None,
    ) -> list[dict[str, Any]]:
        """Queries recent audit records."""

    @abstractmethod
    def close(self):
        """Releases database connections and background worker pools."""
