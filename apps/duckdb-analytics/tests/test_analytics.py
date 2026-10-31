import os
import tempfile
import pytest
from httpx import AsyncClient, ASGITransport

from app.main import app, lifespan

@pytest.fixture
def anyio_backend():
    return "asyncio"

@pytest.fixture
async def client(tmp_path, monkeypatch):
    import app.main as main_mod
    monkeypatch.setattr(main_mod, "PARQUET_DATA_DIR", str(tmp_path))
    monkeypatch.setattr(main_mod, "METABRIDGE5_API_KEY", None)

    async with lifespan(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac

@pytest.mark.asyncio
async def test_health_check(client: AsyncClient):
    resp = await client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["service"] == "duckdb-analytics"

@pytest.mark.asyncio
async def test_simple_select_query(client: AsyncClient):
    resp = await client.post(
        "/api/v1/analytics/query",
        json={"sql_query": "SELECT 42 AS answer, 'EURUSD' AS symbol"},
    )
    assert resp.status_code == 200
    rows = resp.json()
    assert len(rows) == 1
    assert rows[0]["answer"] == 42
    assert rows[0]["symbol"] == "EURUSD"

@pytest.mark.asyncio
async def test_cte_with_query(client: AsyncClient):
    query = """
    WITH numbers AS (
        SELECT 10 AS val UNION ALL SELECT 20 AS val
    )
    SELECT AVG(val) AS avg_val FROM numbers;
    """
    resp = await client.post("/api/v1/analytics/query", json={"sql_query": query})
    assert resp.status_code == 200
    rows = resp.json()
    assert len(rows) == 1
    assert rows[0]["avg_val"] == 15.0

@pytest.mark.asyncio
async def test_rejects_ddl_and_dml(client: AsyncClient):
    forbidden_queries = [
        "DROP TABLE users;",
        "CREATE TABLE test (id INT);",
        "INSERT INTO test VALUES (1);",
        "UPDATE test SET id = 2;",
        "DELETE FROM test WHERE id = 1;",
        "ATTACH 'evil.db';",
        "PRAGMA version;",
        "SELECT 1; DROP TABLE test;",
        "SELECT 1 FROM test; SELECT 2;",
    ]
    for q in forbidden_queries:
        resp = await client.post("/api/v1/analytics/query", json={"sql_query": q})
        assert resp.status_code == 400, f"Query '{q}' should have been rejected"

@pytest.mark.asyncio
async def test_query_parquet_stream(client: AsyncClient):
    resp = await client.post(
        "/api/v1/analytics/query.parquet",
        json={"sql_query": "SELECT 100 AS id, 1.0850 AS close_price"},
    )
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/vnd.apache.parquet"
    content = resp.content
    # Parquet files start with magic bytes PAR1
    assert content.startswith(b"PAR1")
    assert content.endswith(b"PAR1")

@pytest.mark.asyncio
async def test_api_key_auth(monkeypatch, client: AsyncClient):
    import app.main as main_mod

    monkeypatch.setattr(main_mod, "METABRIDGE5_API_KEY", "secret-test-key")

    # Request without key
    resp_unauth = await client.post(
        "/api/v1/analytics/query",
        json={"sql_query": "SELECT 1"},
    )
    assert resp_unauth.status_code == 401

    # Request with invalid key
    resp_bad = await client.post(
        "/api/v1/analytics/query",
        headers={"X-API-Key": "wrong-key"},
        json={"sql_query": "SELECT 1"},
    )
    assert resp_bad.status_code == 401

    # Request with valid X-API-Key
    resp_valid = await client.post(
        "/api/v1/analytics/query",
        headers={"X-API-Key": "secret-test-key"},
        json={"sql_query": "SELECT 1 AS ok"},
    )
    assert resp_valid.status_code == 200
    assert resp_valid.json()[0]["ok"] == 1

    # Request with valid Bearer token
    resp_bearer = await client.post(
        "/api/v1/analytics/query",
        headers={"Authorization": "Bearer secret-test-key"},
        json={"sql_query": "SELECT 2 AS ok"},
    )
    assert resp_bearer.status_code == 200
    assert resp_bearer.json()[0]["ok"] == 2
