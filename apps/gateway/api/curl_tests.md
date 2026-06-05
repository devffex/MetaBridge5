# MetaTrader 5 HTTP Wrapper Endpoint testing Suite

This guide provides a comprehensive list of curl commands to test all mapped MetaTrader 5 terminal wrapper endpoints running inside the Docker container context.

## Host & Configuration Variables

The REST API endpoints are completely stateless and act as a direct proxy to the native `MetaTrader5` library. Path parameters like `{org}`, `{trader}`, `{broker}`, and `{account}` are no longer required.

- **Host**: `http://localhost:8000`

## Authentication

All endpoints under `/api/v1/` require a **Bearer token** in the `Authorization` header. The token must match the `SAVISOR_API_KEY` environment variable set when starting the container.

Set your API key in a shell variable for convenience:

```bash
export SAVISOR_API_KEY="your-secret-api-key-here"
```

Every curl command below includes the authorization header:
```
-H "Authorization: Bearer $SAVISOR_API_KEY"
```

> **Note**: The `GET /` and `GET /health` endpoints do **not** require authentication.

### Unauthenticated Endpoints

```bash
# Root metadata
curl -i -X GET http://localhost:8000/

# Health check
curl -i -X GET http://localhost:8000/health
```

---

## 1. Lifecycle Operations

### Initialize / Shutdown

The native MetaTrader 5 `initialize()` and `shutdown()` operations are handled automatically via the **FastAPI Lifespan Context Manager** on container startup and shutdown. They do not require direct manual HTTP execution.

---

## 3. Diagnostics & Metadata

### Terminal Info (`terminal_info`)

Retrieve connected MT5 terminal settings and client status.

```bash
curl -i -X GET http://localhost:8000/api/v1/terminals/trade/terminal/info \
  -H "Authorization: Bearer $SAVISOR_API_KEY"
```

### Account Info (`account_info`)

Retrieve information on the currently authenticated trading account.

```bash
curl -i -X GET http://localhost:8000/api/v1/terminals/trade/account \
  -H "Authorization: Bearer $SAVISOR_API_KEY"
```

### Version (`version`)

Get the MT5 client build, version, and release date.

```bash
curl -i -X GET http://localhost:8000/api/v1/terminals/trade/version \
  -H "Authorization: Bearer $SAVISOR_API_KEY"
```

### Last Error (`last_error`)

Check the code and description of the last recorded terminal error.

```bash
curl -i -X GET http://localhost:8000/api/v1/terminals/trade/last-error \
  -H "Authorization: Bearer $SAVISOR_API_KEY"
```

---

## 4. Symbol & Watch Management

### Symbols Total (`symbols_total`)

Get the total number of financial instruments available on the server.

```bash
curl -i -X GET http://localhost:8000/api/v1/terminals/trade/symbols/total \
  -H "Authorization: Bearer $SAVISOR_API_KEY"
```

### Symbols Get (`symbols_get`)

Retrieve financial instruments (filterable by `group`).

```bash
curl -i -X GET "http://localhost:8000/api/v1/terminals/trade/symbols?group=Forex" \
  -H "Authorization: Bearer $SAVISOR_API_KEY"
```

### Symbol Select (`symbol_select`)

Add or remove a symbol from the Market Watch window.

```bash
curl -i -X POST http://localhost:8000/api/v1/terminals/trade/symbols/select \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $SAVISOR_API_KEY" \
  -d '{
    "symbol": "EURUSD",
    "enable": true
  }'
```

### Symbol Info (`symbol_info`)

Get complete detail specifications for a symbol.

```bash
curl -i -X POST http://localhost:8000/api/v1/terminals/trade/symbols/info \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $SAVISOR_API_KEY" \
  -d '{
    "symbol": "EURUSD"
  }'
```

### Symbol Info Tick (`symbol_info_tick`)

Fetch the last tick details (bid/ask/last prices) for a symbol.

```bash
curl -i -X POST http://localhost:8000/api/v1/terminals/trade/symbols/info/tick \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $SAVISOR_API_KEY" \
  -d '{
    "symbol": "EURUSD"
  }'
```

---

## 5. Market Depth (Order Book)

### Market Book Add (`market_book_add`)

Subscribe the terminal to market depth events for a specific instrument.

```bash
curl -i -X POST http://localhost:8000/api/v1/terminals/trade/market/book/add \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $SAVISOR_API_KEY" \
  -d '{
    "symbol": "EURUSD"
  }'
```

### Market Book Get (`market_book_get`)

Get the active market depth order book levels.

```bash
curl -i -X GET "http://localhost:8000/api/v1/terminals/trade/market/book/get?symbol=EURUSD" \
  -H "Authorization: Bearer $SAVISOR_API_KEY"
```

### Market Book Release (`market_book_release`)

Unsubscribe the terminal from market depth events for a symbol.

```bash
curl -i -X POST http://localhost:8000/api/v1/terminals/trade/market/book/release \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $SAVISOR_API_KEY" \
  -d '{
    "symbol": "EURUSD"
  }'
```

---

## 6. Rates & Ticks (Historical Data)

### Copy Rates From (`copy_rates_from`)

Get bars starting from a specific timestamp (timeframe enum: `1` = M1, `16385` = H1, `16408` = D1).

```bash
curl -i -X POST http://localhost:8000/api/v1/terminals/trade/market/rates/from \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $SAVISOR_API_KEY" \
  -d '{
    "symbol": "EURUSD",
    "timeframe": 16385,
    "date_from": "2026-06-01T00:00:00Z",
    "count": 100
  }'
```

### Copy Rates From Pos (`copy_rates_from_pos`)

Get bars from a specific index offset.

```bash
curl -i -X POST http://localhost:8000/api/v1/terminals/trade/market/rates/from-pos \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $SAVISOR_API_KEY" \
  -d '{
    "symbol": "EURUSD",
    "timeframe": 1,
    "start_pos": 0,
    "count": 100
  }'
```

### Copy Rates Range (`copy_rates_range`)

Get bars within an absolute date range.

```bash
curl -i -X POST http://localhost:8000/api/v1/terminals/trade/market/rates/range \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $SAVISOR_API_KEY" \
  -d '{
    "symbol": "EURUSD",
    "timeframe": 16385,
    "date_from": "2026-06-01T00:00:00Z",
    "date_to": "2026-06-01T12:00:00Z"
  }'
```

### Copy Ticks From (`copy_ticks_from`)

Get ticks starting from a date (flags: `1` = info, `2` = trade, `-1` = all).

```bash
curl -i -X POST http://localhost:8000/api/v1/terminals/trade/market/ticks/from \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $SAVISOR_API_KEY" \
  -d '{
    "symbol": "EURUSD",
    "date_from": "2026-06-01T12:00:00Z",
    "count": 50,
    "flags": -1
  }'
```

### Copy Ticks Range (`copy_ticks_range`)

Get ticks in an absolute date range.

```bash
curl -i -X POST http://localhost:8000/api/v1/terminals/trade/market/ticks/range \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $SAVISOR_API_KEY" \
  -d '{
    "symbol": "EURUSD",
    "date_from": "2026-06-01T00:00:00Z",
    "date_to": "2026-06-01T01:00:00Z",
    "flags": -1
  }'
```

---

## 7. Trade Orders & Calculus

### Orders Total (`orders_total`)

Get the count of current active pending orders.

```bash
curl -i -X GET http://localhost:8000/api/v1/terminals/trade/orders/total \
  -H "Authorization: Bearer $SAVISOR_API_KEY"
```

### Orders Get (`orders_get`)

List current active pending orders (with optional parameters to filter).

```bash
curl -i -X GET "http://localhost:8000/api/v1/terminals/trade/orders?symbol=EURUSD" \
  -H "Authorization: Bearer $SAVISOR_API_KEY"
```

### Order Check (`order_check`)

Verify margin and trading viability before submitting a trade order.

```bash
curl -i -X POST http://localhost:8000/api/v1/terminals/trade/order/check \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $SAVISOR_API_KEY" \
  -d '{
    "action": 1,
    "symbol": "EURUSD",
    "volume": 0.1,
    "price": 1.10250,
    "type": 0,
    "type_filling": 0
  }'
```

### Order Send (`order_send`)

Submit an active trading transaction request (e.g. buying 0.1 EURUSD).

```bash
curl -i -X POST http://localhost:8000/api/v1/terminals/trade/order \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $SAVISOR_API_KEY" \
  -d '{
    "action": 1,
    "symbol": "EURUSD",
    "volume": 0.1,
    "price": 1.10250,
    "type": 0,
    "type_filling": 0
  }'
```

### Order Calc Profit (`order_calc_profit`)

Calculate estimated profit for a potential buy/sell setup.

```bash
curl -i -X POST http://localhost:8000/api/v1/terminals/trade/order/calc/profit \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $SAVISOR_API_KEY" \
  -d '{
    "action": 0,
    "symbol": "EURUSD",
    "volume": 0.1,
    "price_open": 1.10250,
    "price_close": 1.10350
  }'
```

### Order Calc Margin (`order_calc_margin`)

Calculate the margin required for a specific type of trade.

```bash
curl -i -X POST http://localhost:8000/api/v1/terminals/trade/order/calc/margin \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $SAVISOR_API_KEY" \
  -d '{
    "action": 0,
    "symbol": "EURUSD",
    "volume": 0.1,
    "price": 1.10250
  }'
```

---

## 8. Positions Management

### Positions Total (`positions_total`)

Get the count of active market positions.

```bash
curl -i -X GET http://localhost:8000/api/v1/terminals/trade/positions/total \
  -H "Authorization: Bearer $SAVISOR_API_KEY"
```

### Positions Get (`positions_get`)

Retrieve active market positions (with optional query filters).

```bash
curl -i -X GET "http://localhost:8000/api/v1/terminals/trade/positions?symbol=EURUSD" \
  -H "Authorization: Bearer $SAVISOR_API_KEY"
```

---

## 9. History Queries

### History Orders Total (`history_orders_total`)

Retrieve the count of past orders within a specified date range.

```bash
curl -i -X POST http://localhost:8000/api/v1/terminals/trade/history/orders/total \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $SAVISOR_API_KEY" \
  -d '{
    "date_from": "2026-05-01T00:00:00Z",
    "date_to": "2026-06-01T00:00:00Z"
  }'
```

### History Orders Get (`history_orders_get`)

Get the detailed list of past orders (by range, ticket, or position).

```bash
curl -i -X POST http://localhost:8000/api/v1/terminals/trade/history/orders \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $SAVISOR_API_KEY" \
  -d '{
    "date_from": "2026-05-01T00:00:00Z",
    "date_to": "2026-06-01T00:00:00Z"
  }'
```

### History Deals Total (`history_deals_total`)

Retrieve the count of past execution deals in a range.

```bash
curl -i -X POST http://localhost:8000/api/v1/terminals/trade/history/deals/total \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $SAVISOR_API_KEY" \
  -d '{
    "date_from": "2026-05-01T00:00:00Z",
    "date_to": "2026-06-01T00:00:00Z"
  }'
```

### History Deals Get (`history_deals_get`)

Get the detailed execution deals details (by range, ticket, or position).

```bash
curl -i -X POST http://localhost:8000/api/v1/terminals/trade/history/deals \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $SAVISOR_API_KEY" \
  -d '{
    "date_from": "2026-05-01T00:00:00Z",
    "date_to": "2026-06-01T00:00:00Z"
  }'
```
