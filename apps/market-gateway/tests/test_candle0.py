import pytest

from app.engine.candle0_manager import Candle0Manager


@pytest.mark.asyncio
async def test_candle0_tick_aggregation():
    manager = Candle0Manager(supported_timeframes=["M1", "M5"])

    # Tick 1: at timestamp 1700000010, price 1.0800
    tick1 = {"time": 1700000010, "bid": 1.0800, "ask": 1.0802, "last": 1.0801, "volume": 5}
    states1 = await manager.process_tick("EURUSD", tick1)

    assert "M1" in states1
    m1_c = states1["M1"]
    assert m1_c.time == 1700000000 - (1700000000 % 60)  # bucket start
    assert m1_c.open == 1.0801
    assert m1_c.high == 1.0801
    assert m1_c.low == 1.0801
    assert m1_c.close == 1.0801
    assert m1_c.tick_volume == 5

    # Tick 2: Higher price in same M1 bucket
    tick2 = {"time": 1700000020, "bid": 1.0820, "ask": 1.0822, "last": 1.0821, "volume": 3}
    states2 = await manager.process_tick("EURUSD", tick2)
    m1_c = states2["M1"]
    assert m1_c.high == 1.0821
    assert m1_c.low == 1.0801
    assert m1_c.close == 1.0821
    assert m1_c.tick_volume == 8

    # Tick 3: Lower price in same M1 bucket
    tick3 = {"time": 1700000030, "bid": 1.0790, "ask": 1.0792, "last": 1.0791, "volume": 2}
    states3 = await manager.process_tick("EURUSD", tick3)
    m1_c = states3["M1"]
    assert m1_c.high == 1.0821
    assert m1_c.low == 1.0791
    assert m1_c.close == 1.0791
    assert m1_c.tick_volume == 10


@pytest.mark.asyncio
async def test_candle0_boundary_rollover_and_callback():
    manager = Candle0Manager(supported_timeframes=["M1"])

    closed_candles = []

    async def on_close(symbol, timeframe, closed_candle):
        closed_candles.append((symbol, timeframe, closed_candle))

    manager.register_close_callback(on_close)

    # Initial bucket: 1700000000 (time 1700000015)
    t1 = {"time": 1700000015, "bid": 1.0800, "ask": 1.0802, "last": 1.0801, "volume": 5}
    await manager.process_tick("EURUSD", t1)

    assert len(closed_candles) == 0

    # Cross boundary into next M1 bucket: 1700000060 (time 1700000065)
    t2 = {"time": 1700000065, "bid": 1.0850, "ask": 1.0852, "last": 1.0851, "volume": 4}
    states = await manager.process_tick("EURUSD", t2)

    # Allow background callback tasks to execute
    import asyncio

    await asyncio.sleep(0.05)

    assert len(closed_candles) == 1
    sym, tf, closed = closed_candles[0]
    assert sym == "EURUSD"
    assert tf == "M1"
    assert closed["open"] == 1.0801
    assert closed["close"] == 1.0801

    # New Candle 0 initialized
    m1_new = states["M1"]
    assert m1_new.time == 1700000065 - (1700000065 % 60)
    assert m1_new.open == 1.0851
    assert m1_new.close == 1.0851
