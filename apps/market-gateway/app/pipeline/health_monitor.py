"""
Pipeline Health & Freshness Monitor.
Adopted from the pure-verdict evaluate() design in cifra-connectors/sync_health/verify.py.
"""

from __future__ import annotations

import enum
import time
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any


class Severity(enum.IntEnum):
    OK = 0
    WARN = 1
    ERROR = 2


@dataclass(frozen=True)
class CheckResult:
    severity: Severity
    check: str
    message: str
    context: dict[str, Any] = field(default_factory=dict)


def evaluate_tick_freshness(
    active_symbols: Sequence[dict[str, Any]],
    now_ts: float | None = None,
    warn_threshold_seconds: float = 15.0,
    error_threshold_seconds: float = 45.0,
) -> CheckResult:
    """
    Evaluates price feed freshness across all active Market Watch symbols.
    Flags WARNING or ERROR if any symbol has not received ticks recently.
    """
    reference_now = now_ts or time.time()
    if not active_symbols:
        return CheckResult(
            severity=Severity.OK,
            check="tick_freshness",
            message="No active symbols currently provisioned in watchlist.",
            context={"active_count": 0},
        )

    symbol_ages: dict[str, float] = {}
    stale_symbols: list[dict[str, Any]] = []
    max_age: float = 0.0

    for s in active_symbols:
        sym_name = s.get("name") or s.get("symbol", "UNKNOWN")
        last_time = float(s.get("time") or s.get("last_tick_time") or 0)
        age = max(0.0, reference_now - last_time) if last_time > 0 else 9999.0
        symbol_ages[sym_name] = round(age, 2)
        max_age = max(max_age, age)
        if age > warn_threshold_seconds:
            stale_symbols.append({"symbol": sym_name, "age_seconds": round(age, 1)})

    if max_age > error_threshold_seconds:
        sev = Severity.ERROR
        msg = f"Stale feed detected! {len(stale_symbols)} symbol(s) have not ticked in > {error_threshold_seconds}s (max age: {max_age:.1f}s)"
    elif max_age > warn_threshold_seconds:
        sev = Severity.WARN
        msg = f"Delayed feed: {len(stale_symbols)} symbol(s) have not ticked in > {warn_threshold_seconds}s (max age: {max_age:.1f}s)"
    else:
        sev = Severity.OK
        msg = f"All {len(active_symbols)} active symbols receiving fresh ticks (max age: {max_age:.1f}s)"

    return CheckResult(
        severity=sev,
        check="tick_freshness",
        message=msg,
        context={
            "total_active": len(active_symbols),
            "max_age_seconds": round(max_age, 2),
            "symbol_ages": symbol_ages,
            "stale_symbols": stale_symbols,
        },
    )


def evaluate_stuck_jobs(
    status_registry: dict[str, Any],
    max_age_seconds: float = 180.0,
    now_ts: float | None = None,
) -> CheckResult:
    """
    Evaluates running pipeline ingestion jobs and catches jobs stuck in
    non-terminal states ('in_progress', 'fetching_chunk') past max_age_seconds.
    """
    reference_now = now_ts or time.time()
    stuck_jobs: list[dict[str, Any]] = []

    for sym, job in status_registry.items():
        if isinstance(job, dict):
            status = job.get("status")
            start_time = float(job.get("start_time") or job.get("updated_at") or reference_now)
            age = max(0.0, reference_now - start_time)
            if status in {"in_progress", "fetching_chunk", "uploading"} and age > max_age_seconds:
                stuck_jobs.append(
                    {
                        "symbol": sym,
                        "status": status,
                        "age_seconds": round(age, 1),
                    }
                )

    if stuck_jobs:
        sev = Severity.ERROR
        msg = f"{len(stuck_jobs)} pipeline job(s) stuck in non-terminal state > {max_age_seconds}s"
    else:
        sev = Severity.OK
        msg = "0 stuck pipeline jobs detected."

    return CheckResult(
        severity=sev,
        check="stuck_jobs",
        message=msg,
        context={
            "stuck_count": len(stuck_jobs),
            "stuck_jobs": stuck_jobs,
            "max_age_seconds": max_age_seconds,
        },
    )


def evaluate_pipeline_health(
    active_symbols: Sequence[dict[str, Any]],
    status_registry: dict[str, Any],
    now_ts: float | None = None,
) -> dict[str, Any]:
    """
    Runs all pure evaluation checks and returns a unified diagnostic report.
    """
    reference_now = now_ts or time.time()
    check_freshness = evaluate_tick_freshness(active_symbols, now_ts=reference_now)
    check_stuck = evaluate_stuck_jobs(status_registry, now_ts=reference_now)

    checks = [check_freshness, check_stuck]
    overall_sev = max((c.severity for c in checks), default=Severity.OK)

    return {
        "overall": overall_sev.name,
        "timestamp": int(reference_now),
        "checks": [
            {
                "check": c.check,
                "severity": c.severity.name,
                "message": c.message,
                "context": c.context,
            }
            for c in checks
        ],
    }
