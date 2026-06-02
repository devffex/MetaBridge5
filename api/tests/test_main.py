import os

# Force mock mode for testing
os.environ["METAFORGE_MOCK_MT5"] = "1"

from fastapi.testclient import TestClient

from main import app

client = TestClient(app)


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


def test_get_account_info():
    response = client.get(
        "/api/v1/terminals/savisor/julio/exness/198386280/trade/account"
    )
    assert response.status_code == 200
    data = response.json()
    assert data["login"] == 25115284
    assert data["balance"] == 99511.4
    assert data["currency"] == "USD"


def test_get_positions():
    response = client.get(
        "/api/v1/terminals/savisor/julio/exness/198386280/trade/positions"
    )
    assert response.status_code == 200
    data = response.json()
    assert "positions" in data
    assert len(data["positions"]) == 1
    assert data["positions"][0]["ticket"] == 12345
    assert data["positions"][0]["symbol"] == "EURUSD"
