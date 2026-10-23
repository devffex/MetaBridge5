# Complete API Reference Directory

This document is the exhaustive API reference for all REST endpoints and WebSocket channels exposed by the MetaBridge5 Market Gateway on port `8000`.

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
| `/api/v1/telemetry/stream` | `GET` | No | None | Live Server-Sent Events (SSE) stream yielding real-time pipeline and candle events. |
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
| `/api/v1/pipeline/status` | `GET` | Yes | `symbol` (optional) | Inspect backfill worker status registry, active symbols & paused states. |
| `/api/v1/pipeline/health` | `GET` | Yes | None | Pure-verdict health check: price feed freshness & stuck pipeline job detector. |
| `/api/v1/pipeline/pause` | `POST` | Yes | `symbol` (optional query param) | Pauses ingestion globally or for a specific symbol. |
| `/api/v1/pipeline/resume` | `POST` | Yes | `symbol` (optional query param) | Resumes ingestion globally or for a specific symbol. |
| `/api/v1/pipeline/control` | `POST` | Yes | `PipelineControlRequest` | Bulk or exclusionary pause/resume controls (e.g. ingest ONLY USDJPY). |

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
  "symbols": ["EURUSD", "GBPUSD"],
  "all_symbols": false,
  "source": "active",
  "timeframes": ["M1", "M5", "M15", "M30", "H1", "H4", "D1", "W1", "MN1"],
  "days": 30,
  "candle_count": 100000,
  "date_from": "2024-01-01T00:00:00Z",
  "date_to": "2024-12-31T23:59:59Z"
}
```
* `symbol` *(optional)*: Single asset symbol (e.g. `"EURUSD"`), or `"ALL"` / `"*"` to extract all assets.
* `symbols` *(optional)*: List of explicit symbols to extract (e.g. `["EURUSD", "GBPUSD", "USDJPY"]`).
* `all_symbols` *(optional, bool)*: If `true`, extracts all assets.
* `source` *(optional, string)*: Asset pool when extracting all assets: `"active"` (Market Watch, default) or `"broker"` (full broker catalog).
* `timeframes` *(optional, list)*: Explicit timeframes to extract (e.g. `["M1", "H1", "D1"]`). Defaults to all 9 supported timeframes (`M1`, `M5`, `M15`, `M30`, `H1`, `H4`, `D1`, `W1`, `MN1`).
* `days` *(optional, integer)*: Relative lookback in days (e.g. `30`, `90`, `365`). Automatically calculates `date_from` and `date_to`.
* `candle_count` *(optional, integer)*: Maximum historical bars per timeframe when date range is not specified (default: `100000`).
* `date_from` / `date_to` *(optional, string)*: Explicit ISO 8601 calendar bounds.

### `PipelineControlRequest`
```json
{
  "action": "pause",
  "scope": "exclude",
  "symbols": ["USDJPY"]
}
```
* `scope: "all"` $\to$ Globally pause or resume all data ingestion.
* `scope: "symbols"` $\to$ Pause or resume only the specified list of symbols.
* `scope: "exclude"` $\to$ Keep specified symbols active while pausing all other active symbols (e.g. ingest ONLY `USDJPY`).

---

### Compact Candle Array Format
```json
[timestamp_seconds, open, high, low, close, tick_volume]
```
Example:
```json
[1787778000, 1.16534, 1.16534, 1.16527, 1.16529, 6]
```

