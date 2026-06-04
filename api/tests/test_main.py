import os

# Force mock mode for testing
os.environ["METAFORGE_MOCK_MT5"] = "1"

# Set a known API key for test authentication
os.environ["SAVISOR_API_KEY"] = "test-api-key-for-unit-tests"

from fastapi.testclient import TestClient

from main import app

client = TestClient(app)

AUTH_HEADER = {"Authorization": "Bearer test-api-key-for-unit-tests"}


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
    assert response.json() == {"status": "ok"}


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
    assert response.json() == {"status": "ok"}


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
