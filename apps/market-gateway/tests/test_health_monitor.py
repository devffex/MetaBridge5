from app.pipeline.health_monitor import (
    Severity,
    evaluate_pipeline_health,
    evaluate_stuck_jobs,
    evaluate_tick_freshness,
)


def test_evaluate_tick_freshness_ok():
    now_ts = 1700000100.0
    active = [
        {"name": "EURUSD", "time": 1700000098.0},
        {"name": "GBPUSD", "time": 1700000095.0},
    ]
    res = evaluate_tick_freshness(active, now_ts=now_ts)
    assert res.severity == Severity.OK
    assert "receiving fresh ticks" in res.message


def test_evaluate_tick_freshness_warn_and_error():
    now_ts = 1700000100.0
    # 20s age -> WARN
    active_warn = [{"name": "EURUSD", "time": 1700000080.0}]
    res_warn = evaluate_tick_freshness(active_warn, now_ts=now_ts)
    assert res_warn.severity == Severity.WARN

    # 50s age -> ERROR (stale feed)
    active_err = [{"name": "USDJPY", "time": 1700000050.0}]
    res_err = evaluate_tick_freshness(active_err, now_ts=now_ts)
    assert res_err.severity == Severity.ERROR
    assert "Stale feed detected" in res_err.message


def test_evaluate_stuck_jobs():
    now_ts = 1700001000.0
    # Job running for 500s -> stuck
    registry = {
        "EURUSD": {"status": "in_progress", "start_time": 1700000500.0},
        "GBPUSD": {"status": "completed", "start_time": 1700000100.0},
    }
    res = evaluate_stuck_jobs(registry, max_age_seconds=180.0, now_ts=now_ts)
    assert res.severity == Severity.ERROR
    assert res.context["stuck_count"] == 1


def test_evaluate_pipeline_health_full_verdict():
    now_ts = 1700000100.0
    active = [{"name": "EURUSD", "time": 1700000099.0}]
    registry = {"EURUSD": {"status": "completed", "start_time": 1700000090.0}}

    report = evaluate_pipeline_health(active, registry, now_ts=now_ts)
    assert report["overall"] == "OK"
    assert len(report["checks"]) == 2
