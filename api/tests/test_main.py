import os
from collections.abc import Generator

import pytest

# Force mock mode for testing
os.environ["METAFORGE_MOCK_MT5"] = "1"
os.environ["SAVISOR_API_KEY"] = "test-api-key-for-unit-tests"

from fastapi.testclient import TestClient

from main import app
from routers.trading import mt5

client = TestClient(app)

AUTH_HEADER = {"Authorization": "Bearer test-api-key-for-unit-tests"}


# Helper fixture to temporarily change MT5 connection state during test
@pytest.fixture
def mock_mt5_degrade() -> Generator[None]:
    # Cache original connected state
    original_connected = True
    info = mt5.terminal_info()
    if info is not None:
        original_connected = getattr(info, "connected", True)

    # Degrade connection
    class DegradedInfo:
        def __init__(self):
            self.connected = False

        def _asdict(self):
            return {"connected": False}

    mt5.terminal_info = lambda *args, **kwargs: DegradedInfo()
    yield

    # Restore original method
    class RestoredInfo:
        def __init__(self, conn):
            self.connected = conn

        def _asdict(self):
            return {"connected": self.connected}

    mt5.terminal_info = lambda *args, **kwargs: RestoredInfo(original_connected)


# ------------------------------------------------------------------
# Unauthenticated public endpoints
# ------------------------------------------------------------------


def test_read_root():
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "online"
    assert "version" in data


def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["mt5_connected"] is True
    assert "disk" in data


def test_health_check_degraded(mock_mt5_degrade):
    response = client.get("/health")
    assert response.status_code == 503
    data = response.json()
    assert data["status"] == "degraded"
    assert data["mt5_connected"] is False


# ------------------------------------------------------------------
# Authentication enforcement
# ------------------------------------------------------------------


def test_unauthenticated_request_returns_401():
    """Protected endpoints must reject requests without credentials."""
    response = client.get("/api/v1/terminals/trade/account")
    assert response.status_code == 401
    data = response.json()
    assert "detail" in data
    assert response.headers.get("WWW-Authenticate") == "Bearer"


def test_wrong_api_key_returns_401():
    """Protected endpoints must reject requests with an incorrect key."""
    response = client.get(
        "/api/v1/terminals/trade/account",
        headers={"Authorization": "Bearer wrong-key"},
    )
    assert response.status_code == 401
    data = response.json()
    assert "detail" in data
    assert response.headers.get("WWW-Authenticate") == "Bearer"


def test_health_no_auth_required():
    """The health endpoint must remain accessible without authentication."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["mt5_connected"] is True


# ------------------------------------------------------------------
# Authenticated endpoint access
# ------------------------------------------------------------------


def test_get_account_info():
    response = client.get(
        "/api/v1/terminals/trade/account",
        headers=AUTH_HEADER,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["login"] == 25115284
    assert data["balance"] == 99511.4
    assert data["currency"] == "USD"


def test_get_positions():
    response = client.get(
        "/api/v1/terminals/trade/positions",
        headers=AUTH_HEADER,
    )
    assert response.status_code == 200
    data = response.json()
    assert "positions" in data
    assert len(data["positions"]) == 1
    assert data["positions"][0]["ticket"] == 12345
    assert data["positions"][0]["symbol"] == "EURUSD"


def test_copy_rates_from_pos_limits():
    response = client.post(
        "/api/v1/terminals/trade/market/rates/from-pos",
        headers=AUTH_HEADER,
        json={
            "symbol": "EURUSD",
            "timeframe": 1,
            "start_pos": 0,
            "count": 15000,  # Capped count test
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert "rates" in data
