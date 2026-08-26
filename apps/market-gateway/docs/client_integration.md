# Client Integration Guide

This guide provides integration recipes for integrating web charts, algorithmic trading bots, and machine learning pipelines with the Savisor Market Node.

---

## 1. Web Frontend: React + TradingView Lightweight Charts

```typescript
import { createChart, ISeriesApi } from "lightweight-charts";

export class MarketChartClient {
  private series: ISeriesApi<"Candlestick">;
  private ws: WebSocket | null = null;

  constructor(container: HTMLElement, private symbol: string = "EURUSD", private timeframe: string = "H1") {
    const chart = createChart(container, { width: 900, height: 500 });
    this.series = chart.addCandlestickSeries();
  }

  // 1. Fast Warmup from jsDelivr Multi-CDN
  async warmup() {
    const cdnUrl = `https://cdn.jsdelivr.net/gh/your_org/dataset@main/data/${this.symbol}/${this.timeframe}/recent.json`;
    const res = await fetch(cdnUrl);
    const rawCandles: [number, number, number, number, number, number][] = await res.json();
    
    const history = rawCandles.map(([time, open, high, low, close]) => ({
      time, open, high, low, close
    }));
    this.series.setData(history);
  }

  // 2. Stream Live Candle 0 & Ticks over WebSocket
  connectStream(wsHost: string = "localhost:8000") {
    this.ws = new WebSocket(`ws://${wsHost}/api/v1/market/ws/${this.symbol}`);
    
    this.ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      if (data.candle0 && data.candle0[this.timeframe]) {
        const [time, open, high, low, close] = data.candle0[this.timeframe];
        this.series.update({ time, open, high, low, close });
      }
    };
  }

  disconnect() {
    if (this.ws) {
      this.ws.close();
    }
  }
}
```

---

## 2. Algorithmic Trading Bot: Python (Warmup + Live WebSocket)

```python
import asyncio
import json
import httpx
import websockets

async def run_trading_bot(symbol: str = "EURUSD", timeframe: str = "M1"):
    # 1. Warmup from CDN
    async with httpx.AsyncClient() as client:
        res = await client.get(
            f"https://cdn.jsdelivr.net/gh/your_org/dataset@main/data/{symbol}/{timeframe}/recent.json"
        )
        history = res.json()
        print(f"[{symbol}] Loaded {len(history)} historical bars for indicator warmup.")

    # 2. Live Signal Loop
    uri = f"ws://localhost:8000/api/v1/market/ws/{symbol}"
    async with websockets.connect(uri) as ws:
        print(f"[{symbol}] Connected to live market stream.")
        async for message in ws:
            data = json.loads(message)
            if data.get("type") in ("snapshot", "tick") and timeframe in data.get("candle0", {}):
                t, o, h, l, c, vol, bid, ask = data["candle0"][timeframe]
                print(f"[{symbol} {timeframe}] Live Bar -> Close: {c} | Bid: {bid} | Ask: {ask} | Vol: {vol}")

if __name__ == "__main__":
    asyncio.run(run_trading_bot())
```

---

## 3. Machine Learning & Analytics: DuckDB / Polars Direct Query

```python
import duckdb

# Query Parquet partitions directly across the global Multi-CDN
df = duckdb.query("""
    SELECT 
        to_timestamp(time) AS timestamp,
        open, high, low, close, tick_volume,
        (close - open) / open * 100 AS return_pct
    FROM 'https://cdn.jsdelivr.net/gh/your_org/dataset@main/data/EURUSD/H1/history.parquet'
    WHERE time >= 1770000000
    ORDER BY time ASC
""").df()

print(df.head(10))
```
