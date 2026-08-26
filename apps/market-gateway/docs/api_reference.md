# Complete API Reference Directory

This document is the exhaustive API reference for all REST endpoints and WebSocket channels exposed by the Savisor Market Node on port `8000`.

---

## 1. Authentication

Protected endpoints require the API key passed in the `X-API-Key` HTTP header:

```text
X-API-Key: your_secret_api_key_here
```

---

## 2. API Endpoints Directory

| Endpoint | Method | Auth Required | Parameters / Body | Description |
|---|---|---|---|---|
| `/health` | `GET` | No | None | Container and daemon liveness probe. |
| `/ready` | `GET` | No | None | Node readiness probe. |
| `/metrics` | `GET` | No | None | Prometheus telemetry scrape endpoint. |
| `/api/v1/terminal/logs` | `GET` | Yes | `lines` (default: 100), `date` (YYYYMMDD) | Retrieve and tail raw MT5 platform logs. |
| `/api/v1/telemetry/traces` | `GET` | Yes | `limit`, `symbol`, `event`, `component` | Query internal SQLite WAL audit traces. |
| `/api/v1/symbols/broker` | `GET` | Yes | `group` (optional glob pattern) | Query broker instrument catalog. |
| `/api/v1/symbols/active` | `GET` | Yes | None | List actively tracked symbols in Market Watch. |
| `/api/v1/symbols/active` | `POST` | Yes | `SymbolProvisionRequest` | Provision asset and trigger auto-backfill. |
| `/api/v1/symbols/active/{symbol}` | `DELETE` | Yes | Path: `symbol` | De-provision symbol from active watchlist. |
| `/api/v1/market/candle0` | `GET` | Yes | `symbol`, `timeframe` | Retrieve in-flight Candle 0 state. |
| `/api/v1/market/candle0/all` | `GET` | Yes | `symbol` | Active Candle 0 states across all timeframes. |
| `/api/v1/market/ws/{symbol}` | `WS` | No | Path: `symbol` | Real-time WebSocket streaming live ticks & Candle 0. |
| `/api/v1/market/rates` | `GET` | Yes | `symbol`, `timeframe`, `count` | Retrieve cached candle array from MT5. |
| `/api/v1/market/rates/range` | `GET` | Yes | `symbol`, `timeframe`, `date_from`, `date_to` | Retrieve candle array by ISO 8601 date range. |
| `/api/v1/market/rates/from` | `GET` | Yes | `symbol`, `timeframe`, `date_from`, `count` | Retrieve candle array starting from timestamp. |
| `/api/v1/pipeline/backfill` | `POST` | Yes | `BackfillRequest` | Trigger deep historical backfill (chunked or date range). |
| `/api/v1/pipeline/status` | `GET` | Yes | `symbol` (optional) | Inspect backfill worker status registry & active pause state. |
| `/api/v1/pipeline/pause` | `POST` | Yes | None | Pauses historical data extraction and storage push. |
| `/api/v1/pipeline/resume` | `POST` | Yes | None | Resumes historical data extraction and storage push. |

---

## 3. Data Models & Schemas

### `SymbolProvisionRequest`
```json
{
  "symbol": "EURUSD",
  "auto_backfill": true,
  "candle_count": 10000
}
```

### `BackfillRequest`
```json
{
  "symbol": "EURUSD",
  "timeframes": ["M1", "M5", "M15", "M30", "H1", "H4", "D1"],
  "candle_count": 100000,
  "date_from": "2018-01-01T00:00:00Z",
  "date_to": "2026-08-26T00:00:00Z"
}
```

### Compact Candle Array Format
```json
[timestamp_seconds, open, high, low, close, tick_volume]
```
Example:
```json
[1787778000, 1.16534, 1.16534, 1.16527, 1.16529, 6]
```
