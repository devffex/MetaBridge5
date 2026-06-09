# Savisor Chart Analysis Gateway

The Chart Analysis Gateway is a lightweight, high-performance API server designed to stream financial asset price data from the MetaTrader 5 terminal running under Wine to a TradingView-like React frontend.

It utilizes the **Optimized Pass-Through Caching Pattern** (caching in-memory in FastAPI and React while reading directly from MT5's native broker `.hc` binary files) and the **Compact JSON Array-of-Arrays Data Protocol** to achieve a **55%+ reduction in payload size** with 100% native web compatibility.

---

## 1. Quick Start & Execution

### Build the Image
To build the Docker image natively using `uv` dependency management:
```bash
make build-chart-gateway
```

### Run the Container (Mock MT5 Mode)
To run the container locally with instant mock data (no active broker connection required):
```bash
docker rm -f savisor-chart-gateway-run || true && \
docker run -d --name savisor-chart-gateway-run \
  -p 8000:8000 \
  -p 5900:5900 \
  -e SAVISOR_API_KEY="test-api-key" \
  -e VNC_PASSWORD="test-vnc-password" \
  -e METAFORGE_MOCK_MT5="1" \
  savisor-chart-gateway:latest
```

### Verify Container Health
```bash
sleep 3 && curl -i http://localhost:8000/health
```

---

## 2. Credentials & Configuration

*   **API Gateway Port**: `8000` (handles REST & WebSockets)
*   **VNC Display Port**: `5900` (To view the Wine window and MT5 GUI using a VNC Viewer client)
*   **API Security Header**: `X-API-Key: test-api-key`
*   **VNC Connection Password**: `test-vnc-password`
*   **Runtime Mode**: `METAFORGE_MOCK_MT5=1` (Enabled for instant API testing/mock rates. To connect to a live broker account, restart the container without this variable).

---

## 3. API Endpoint Directory

### A. Health Check (Public)
*   **Path**: `GET http://localhost:8000/health`
*   **Security**: No authentication required.
*   **Test Command**:
    ```bash
    curl -i http://localhost:8000/health
    ```

### B. Fetch Historical Rates (Compact JSON)
*   **Path**: `GET http://localhost:8000/api/v1/chart/rates`
*   **Security**: Requires `X-API-Key: test-api-key` header.
*   **Query Parameters**:
    *   `symbol` (required): Asset ticker (e.g. `EURUSD`)
    *   `timeframe` (optional): `M1`, `M5`, `M15`, `H1`, `H4`, `D1` (default: `H1`)
    *   `count` (optional): Number of candles to return, up to 10000 (default: `500`)
    *   `start_pos` (optional): Starting candle index (default: `0`, representing the active candle)
*   **Test Command**:
    ```bash
    curl -i -H "X-API-Key: test-api-key" "http://localhost:8000/api/v1/chart/rates?symbol=EURUSD&timeframe=M5&count=5"
    ```
*   **Sample Response**:
    `[[1774329200, 1.0824, 1.083, 1.082, 1.0828, 150], ...]` *(Format: `[[time, open, high, low, close, volume], ...]`)*

---

### C. Active Symbols Management (Dynamic Provisioning)
Allows the React frontend to add or remove assets tracked by the container.

*   **List Active Pairs**: `GET http://localhost:8000/api/v1/symbols/active`
    ```bash
    curl -i -H "X-API-Key: test-api-key" "http://localhost:8000/api/v1/symbols/active"
    ```
*   **Add/Provision Pair**: `POST http://localhost:8000/api/v1/symbols/active`
    *   *Body*: `{"symbol": "EURUSD"}`
    ```bash
    curl -i -X POST -H "X-API-Key: test-api-key" -H "Content-Type: application/json" -d '{"symbol": "EURUSD"}' "http://localhost:8000/api/v1/symbols/active"
    ```
*   **Remove/Deprovision Pair**: `DELETE http://localhost:8000/api/v1/symbols/active/{symbol}`
    ```bash
    curl -i -X DELETE -H "X-API-Key: test-api-key" "http://localhost:8000/api/v1/symbols/active/EURUSD"
    ```

---

### D. WebSockets Real-Time Tick Stream
*   **Path**: `ws://localhost:8000/api/v1/chart/ws/{symbol}`
*   **Authentication**: Bypassed for connection handshake simplicity.
*   **Test Command** (requires `wscat`):
    ```bash
    wscat -c ws://localhost:8000/api/v1/chart/ws/EURUSD
    ```
*   **Sample Tick Stream Frame**:
    `[1774329205, 1.0825, 1.0827, 1.0826, 15]` *(Format: `[time, bid, ask, last, volume]`)*

---

## 4. Container Logs Audit

To check uvicorn transactions, gRPC connections, and Wine events inside the container:
```bash
docker logs savisor-chart-gateway-run
```
