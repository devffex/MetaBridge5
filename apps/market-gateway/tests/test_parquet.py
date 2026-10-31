import json

from app.pipeline.parquet_exporter import (
    dataframe_to_compact_json_bytes,
    dataframe_to_parquet_bytes,
    merge_rates_with_parquet,
    parquet_bytes_to_dataframe,
    rates_to_dataframe,
)


def test_rates_to_dataframe():
    raw_rates = [
        {"time": 1700000060, "open": 1.0850, "high": 1.0860, "low": 1.0840, "close": 1.0855, "tick_volume": 120},
        {"time": 1700000000, "open": 1.0800, "high": 1.0850, "low": 1.0790, "close": 1.0845, "tick_volume": 100},
        # Duplicate timestamp - should keep latest
        {"time": 1700000000, "open": 1.0800, "high": 1.0852, "low": 1.0790, "close": 1.0849, "tick_volume": 110},
    ]

    df = rates_to_dataframe(raw_rates)
    assert len(df) == 2
    assert list(df.columns) == ["time", "open", "high", "low", "close", "tick_volume"]
    # Check strictly ascending order
    assert df.iloc[0]["time"] == 1700000000
    assert df.iloc[0]["close"] == 1.0849
    assert df.iloc[1]["time"] == 1700000060


def test_parquet_round_trip():
    raw_rates = [
        {"time": 1700000000, "open": 1.0800, "high": 1.0850, "low": 1.0790, "close": 1.0845, "tick_volume": 100},
        {"time": 1700000060, "open": 1.0850, "high": 1.0860, "low": 1.0840, "close": 1.0855, "tick_volume": 120},
    ]
    df = rates_to_dataframe(raw_rates)
    parquet_bytes = dataframe_to_parquet_bytes(df)
    assert len(parquet_bytes) > 0

    df_recovered = parquet_bytes_to_dataframe(parquet_bytes)
    assert len(df_recovered) == 2
    assert df_recovered.iloc[0]["time"] == 1700000000
    assert df_recovered.iloc[1]["close"] == 1.0855


def test_compact_json_serialization():
    raw_rates = [
        {"time": 1700000000, "open": 1.0800, "high": 1.0850, "low": 1.0790, "close": 1.0845, "tick_volume": 100},
        {"time": 1700000060, "open": 1.0850, "high": 1.0860, "low": 1.0840, "close": 1.0855, "tick_volume": 120},
    ]
    df = rates_to_dataframe(raw_rates)
    json_bytes = dataframe_to_compact_json_bytes(df)
    parsed = json.loads(json_bytes.decode("utf-8"))

    assert len(parsed) == 2
    # Check compact array structure: [time, open, high, low, close, volume]
    assert parsed[0] == [1700000000, 1.08, 1.085, 1.079, 1.0845, 100]


def test_merge_rates_with_parquet():
    initial_rates = [
        {"time": 1700000000, "open": 1.0800, "high": 1.0850, "low": 1.0790, "close": 1.0845, "tick_volume": 100},
    ]
    df_initial = rates_to_dataframe(initial_rates)
    initial_parquet = dataframe_to_parquet_bytes(df_initial)

    new_rates = [
        {"time": 1700000060, "open": 1.0850, "high": 1.0860, "low": 1.0840, "close": 1.0855, "tick_volume": 120},
    ]

    merged_df = merge_rates_with_parquet(initial_parquet, new_rates)
    assert len(merged_df) == 2
    assert merged_df.iloc[0]["time"] == 1700000000
    assert merged_df.iloc[1]["time"] == 1700000060


def test_empty_rates():
    df = rates_to_dataframe([])
    assert len(df) == 0
    assert df.columns == ["time", "open", "high", "low", "close", "tick_volume"]
    assert df.to_compact_json_bytes() == b"[]"


def test_corrupt_parquet_merge_fallback():
    new_rates = [
        {"time": 1700000000, "open": 1.08, "high": 1.09, "low": 1.07, "close": 1.085, "tick_volume": 50}
    ]
    # Passing garbage bytes shouldn't crash; it safely falls back to new_rates
    merged = merge_rates_with_parquet(b"corrupt-data", new_rates)
    assert len(merged) == 1
    assert merged.iloc[0]["time"] == 1700000000

