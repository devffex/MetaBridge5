import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import WebSocketDisconnect
from starlette.testclient import TestClient

# Set API key for testing
os.environ["METABRIDGE5_API_KEY"] = "test_key_123"

import app.main as main_mod
from app.main import app


@pytest.fixture
def client():
    # Setup mock grpc_client on main module
    mock_grpc = MagicMock()
    mock_grpc.get_health.return_value = {"status": "ok", "service": "test"}
    mock_grpc.get_rates_from_pos.return_value = [
        {"time": 1700000000, "open": 1.0800, "high": 1.0850, "low": 1.0790, "close": 1.0845, "tick_volume": 100},
        {"time": 1700003600, "open": 1.0845, "high": 1.0860, "low": 1.0830, "close": 1.0855, "tick_volume": 120},
    ]
    mock_grpc.select_symbol.return_value = True
    mock_grpc.get_symbol_info_tick.return_value = None

    def mock_get_symbols(group="", selected_only=False):
        all_syms = [
            {"name": "EURUSD", "visible": True, "select": True},
            {"name": "GBPUSD", "visible": True, "select": True},
            {"name": "USDJPY", "visible": False, "select": False},
        ]
        if selected_only:
            return [s for s in all_syms if s.get("visible") or s.get("select")]
        return all_syms

    mock_grpc.get_symbols.side_effect = mock_get_symbols

    with patch.object(main_mod, "grpc_client", mock_grpc), TestClient(app) as c:
        # Re-ensure mock grpc client after lifespan startup
        main_mod.grpc_client = mock_grpc
        if main_mod.backfill_worker:
            main_mod.backfill_worker.grpc_client = mock_grpc
        yield c


def test_health_endpoint(client):
    res = client.get("/health")
    assert res.status_code == 200
    data = res.json()
    assert "node" in data
    assert data["node"] == "metabridge5-node"


def test_metrics_endpoint(client):
    res = client.get("/metrics")
    assert res.status_code == 200
    assert "metabridge5_ticks_processed_total" in res.text


def test_ready_endpoint(client):
    res = client.get("/ready")
    assert res.status_code == 200
    assert res.json() == {"status": "ready"}


def test_api_key_auth(client):
    # Without header -> 401
    res = client.get("/api/v1/market/rates?symbol=EURUSD&timeframe=H1")
    assert res.status_code == 401

    # With invalid header -> 401
    res = client.get("/api/v1/market/rates?symbol=EURUSD&timeframe=H1", headers={"X-API-Key": "wrong"})
    assert res.status_code == 401

    # With valid header on /api/v1/market/rates -> 200
    res = client.get("/api/v1/market/rates?symbol=EURUSD&timeframe=H1", headers={"X-API-Key": "test_key_123"})
    assert res.status_code == 200
    data = res.json()
    assert isinstance(data, list)
    assert len(data) == 2
    # Compact candle format: [time, open, high, low, close, volume]
    assert data[0] == [1700000000, 1.0800, 1.0850, 1.0790, 1.0845, 100]

    # Backward compatibility: /api/v1/chart/rates also returns 200
    res_chart = client.get("/api/v1/chart/rates?symbol=EURUSD&timeframe=H1", headers={"X-API-Key": "test_key_123"})
    assert res_chart.status_code == 200


@pytest.mark.asyncio
async def test_candle0_api(client):
    # Inject a tick into candle_manager
    tick = {"time": 1700000010, "bid": 1.0850, "ask": 1.0852, "last": 1.0851, "volume": 15}
    await main_mod.candle_manager.process_tick("EURUSD", tick)

    res = client.get(
        "/api/v1/market/candle0?symbol=EURUSD&timeframe=M1",
        headers={"X-API-Key": "test_key_123"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["open"] == 1.0851
    assert data["close"] == 1.0851
    assert data["tick_volume"] == 15

    # Test market candle0 all
    res_all = client.get(
        "/api/v1/market/candle0/all?symbol=EURUSD",
        headers={"X-API-Key": "test_key_123"},
    )
    assert res_all.status_code == 200
    assert "M1" in res_all.json()

    # Backward compatibility: /api/v1/chart/candle0 also returns 200
    res_chart = client.get(
        "/api/v1/chart/candle0?symbol=EURUSD&timeframe=M1",
        headers={"X-API-Key": "test_key_123"},
    )
    assert res_chart.status_code == 200


def test_pipeline_status_and_pause_resume(client):
    # Check default status
    res = client.get(
        "/api/v1/pipeline/status",
        headers={"X-API-Key": "test_key_123"},
    )
    assert res.status_code == 200
    data = res.json()
    assert "global_paused" in data
    assert data["global_paused"] is False

    # Pause pipeline globally
    res_pause = client.post(
        "/api/v1/pipeline/pause",
        headers={"X-API-Key": "test_key_123"},
    )
    assert res_pause.status_code == 200
    assert res_pause.json()["status"] == "paused"
    assert res_pause.json()["global_paused"] is True

    # Resume pipeline globally
    res_resume = client.post(
        "/api/v1/pipeline/resume",
        headers={"X-API-Key": "test_key_123"},
    )
    assert res_resume.status_code == 200
    assert res_resume.json()["status"] == "active"
    assert res_resume.json()["global_paused"] is False


def test_pipeline_per_symbol_and_bulk_control(client):
    # Per-symbol pause
    res = client.post(
        "/api/v1/pipeline/pause?symbol=EURUSD",
        headers={"X-API-Key": "test_key_123"},
    )
    assert res.status_code == 200
    assert "EURUSD" in res.json()["paused_symbols"]

    # Check status for EURUSD
    res_status = client.get(
        "/api/v1/pipeline/status?symbol=EURUSD",
        headers={"X-API-Key": "test_key_123"},
    )
    assert res_status.status_code == 200
    assert res_status.json()["symbol_paused"] is True

    # Bulk control: exclusive ingest USDJPY (pauses all other symbols)
    res_bulk = client.post(
        "/api/v1/pipeline/control",
        json={"action": "pause", "scope": "exclude", "symbols": ["USDJPY"]},
        headers={"X-API-Key": "test_key_123"},
    )
    assert res_bulk.status_code == 200
    assert res_bulk.json()["active_only"] == ["USDJPY"]

    # Resume all
    res_all = client.post(
        "/api/v1/pipeline/control",
        json={"action": "resume", "scope": "all"},
        headers={"X-API-Key": "test_key_123"},
    )
    assert res_all.status_code == 200
    assert res_all.json()["global_paused"] is False


def test_pipeline_health_endpoint(client):
    res = client.get(
        "/api/v1/pipeline/health",
        headers={"X-API-Key": "test_key_123"},
    )
    assert res.status_code == 200
    data = res.json()
    assert "overall" in data
    assert "checks" in data
    assert len(data["checks"]) >= 2


@pytest.mark.asyncio
async def test_telemetry_event_broadcaster():
    from app.telemetry.event_broadcaster import EventBroadcaster

    eb = EventBroadcaster()
    gen = eb.subscribe()
    first_item = await anext(gen)
    assert "connected" in first_item

    eb.broadcast("candle_closed", {"symbol": "EURUSD", "close": 1.0850})
    second_item = await anext(gen)
    assert "candle_closed" in second_item
    assert "EURUSD" in second_item
    await gen.aclose()


def test_terminal_logs_endpoint(client, tmp_path):
    # Test fallback when directory does not exist
    res = client.get("/api/v1/terminal/logs", headers={"X-API-Key": "test_key_123"})
    assert res.status_code == 200
    data = res.json()
    assert "logs" in data or "lines" in data

    # Test reading actual log file
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    log_file = log_dir / "20260826.log"
    log_content = "2026.08.26 12:00:00.000 Terminal MetaTrader 5 build 4320 started\n2026.08.26 12:00:01.000 Trade account 123456 logged in\n"
    log_file.write_bytes(log_content.encode("utf-16-le"))

    with patch("app.main.Path") as mock_path_cls:
        # Provide simulated log dir
        mock_path_instance = MagicMock()
        mock_path_instance.exists.return_value = True
        mock_path_instance.glob.return_value = [log_file]
        mock_path_cls.return_value = mock_path_instance

        res_logs = client.get("/api/v1/terminal/logs?lines=5", headers={"X-API-Key": "test_key_123"})
        assert res_logs.status_code == 200
        logs_data = res_logs.json()
        assert "lines" in logs_data
        assert logs_data["returned_lines"] == 2
        assert "MetaTrader 5" in logs_data["lines"][0]


@pytest.mark.asyncio
async def test_websocket_snapshot():
    # Pre-populate candle_manager
    from app.engine.candle0_manager import Candle0State
    from app.main import websocket_endpoint

    main_mod.candle_manager._states[("EURUSD", "M1")] = Candle0State(
        time=1700000000,
        open=1.0850,
        high=1.0855,
        low=1.0849,
        close=1.0852,
        tick_volume=10,
        last_tick_time=1700000010,
        bid=1.0852,
        ask=1.0853,
    )

    mock_ws = AsyncMock()
    mock_ws.receive_text.side_effect = WebSocketDisconnect()

    await websocket_endpoint(mock_ws, "EURUSD")

    mock_ws.accept.assert_awaited_once()
    mock_ws.send_json.assert_awaited_once()
    sent_data = mock_ws.send_json.call_args[0][0]
    assert sent_data["type"] == "snapshot"
    assert sent_data["symbol"] == "EURUSD"
    assert "M1" in sent_data["candle0"]
    # Compact candle: [time, open, high, low, close, volume, bid, ask]
    assert sent_data["candle0"]["M1"] == [1700000000, 1.0850, 1.0855, 1.0849, 1.0852, 10, 1.0852, 1.0853]


def test_pipeline_sync_interval_endpoints(client):
    # Test GET interval
    res = client.get("/api/v1/pipeline/interval", headers={"X-API-Key": "test_key_123"})
    assert res.status_code == 200
    data = res.json()
    assert "active_sync_interval" in data
    assert "supported_intervals" in data
    assert data["active_sync_interval"] in ["D1", "1D"]

    # Test POST interval update with alias '1h'
    res_update = client.post(
        "/api/v1/pipeline/interval?interval=1h",
        headers={"X-API-Key": "test_key_123"},
    )
    assert res_update.status_code == 200
    assert res_update.json()["active_sync_interval"] == "H1"

    # Test POST interval update with canonical 'W1'
    res_w1 = client.post(
        "/api/v1/pipeline/interval?interval=W1",
        headers={"X-API-Key": "test_key_123"},
    )
    assert res_w1.status_code == 200
    assert res_w1.json()["active_sync_interval"] == "W1"

    # Test POST invalid interval
    res_invalid = client.post(
        "/api/v1/pipeline/interval?interval=invalid_interval",
        headers={"X-API-Key": "test_key_123"},
    )
    assert res_invalid.status_code == 400

    # Reset back to D1
    client.post("/api/v1/pipeline/interval?interval=D1", headers={"X-API-Key": "test_key_123"})


def test_pipeline_backfill_single_symbol(client):
    res = client.post(
        "/api/v1/pipeline/backfill",
        json={"symbol": "EURUSD", "candle_count": 5000},
        headers={"X-API-Key": "test_key_123"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "triggered"
    assert data["symbols"] == ["EURUSD"]
    assert data["total_symbols"] == 1


def test_pipeline_backfill_multiple_symbols(client):
    res = client.post(
        "/api/v1/pipeline/backfill",
        json={"symbols": ["EURUSD", "GBPUSD"], "timeframes": ["M1", "H1"]},
        headers={"X-API-Key": "test_key_123"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "triggered"
    assert data["symbols"] == ["EURUSD", "GBPUSD"]
    assert data["total_symbols"] == 2
    assert data["timeframes"] == ["M1", "H1"]


def test_pipeline_backfill_all_symbols_active(client):
    # Tests all_symbols=True defaults to active Market Watch symbols (EURUSD, GBPUSD)
    res = client.post(
        "/api/v1/pipeline/backfill",
        json={"all_symbols": True},
        headers={"X-API-Key": "test_key_123"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "triggered"
    assert "EURUSD" in data["symbols"]
    assert "GBPUSD" in data["symbols"]
    assert data["total_symbols"] == 2


def test_pipeline_backfill_all_symbols_broker(client):
    # Tests all_symbols=True with source="broker" returns all broker catalog symbols (EURUSD, GBPUSD, USDJPY)
    res = client.post(
        "/api/v1/pipeline/backfill",
        json={"all_symbols": True, "source": "broker"},
        headers={"X-API-Key": "test_key_123"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "triggered"
    assert set(data["symbols"]) == {"EURUSD", "GBPUSD", "USDJPY"}
    assert data["total_symbols"] == 3


def test_pipeline_backfill_days_relative_calculation(client):
    res = client.post(
        "/api/v1/pipeline/backfill",
        json={"symbol": "EURUSD", "days": 30},
        headers={"X-API-Key": "test_key_123"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "triggered"
    assert data["days"] == 30
    assert data["date_from"] is not None
    assert data["date_to"] is not None
    assert "T" in data["date_from"]
    assert "T" in data["date_to"]

