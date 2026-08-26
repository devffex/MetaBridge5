import os
from unittest.mock import MagicMock, patch

import pytest
from starlette.testclient import TestClient

# Set API key for testing
os.environ["SAVISOR_API_KEY"] = "test_key_123"

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
    assert data["node"] == "savisor-node"


def test_metrics_endpoint(client):
    res = client.get("/metrics")
    assert res.status_code == 200
    assert "savisor_ticks_processed_total" in res.text


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


def test_pipeline_status(client):
    res = client.get(
        "/api/v1/pipeline/status",
        headers={"X-API-Key": "test_key_123"},
    )
    assert res.status_code == 200
    assert isinstance(res.json(), dict)
