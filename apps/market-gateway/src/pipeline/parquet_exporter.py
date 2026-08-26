import io
import json
import logging
from typing import Any

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

logger = logging.getLogger("pipeline.parquet_exporter")

# Schema for historical candle datasets
CANDLE_ARROW_SCHEMA = pa.schema(
    [
        pa.field("time", pa.int64(), nullable=False),
        pa.field("open", pa.float64(), nullable=False),
        pa.field("high", pa.float64(), nullable=False),
        pa.field("low", pa.float64(), nullable=False),
        pa.field("close", pa.float64(), nullable=False),
        pa.field("tick_volume", pa.int64(), nullable=False),
    ]
)


def rates_to_dataframe(rates: list[dict[str, Any]]) -> pd.DataFrame:
    """
    Converts MT5 rates list of dictionaries into a normalized, sorted,
    and deduplicated pandas DataFrame.
    """
    if not rates:
        return pd.DataFrame(columns=["time", "open", "high", "low", "close", "tick_volume"])

    df = pd.DataFrame(rates)

    # Standardize column names
    col_mapping = {
        "time": "time",
        "open": "open",
        "high": "high",
        "low": "low",
        "close": "close",
        "tick_volume": "tick_volume",
        "volume": "tick_volume",
    }
    df = df.rename(columns={k: v for k, v in col_mapping.items() if k in df.columns})

    # Ensure required columns exist
    for col in ["time", "open", "high", "low", "close"]:
        if col not in df.columns:
            raise ValueError(f"Missing required candle column: {col}")
    if "tick_volume" not in df.columns:
        df["tick_volume"] = 0

    # Type casting
    df["time"] = df["time"].astype("int64")
    df["open"] = df["open"].astype("float64")
    df["high"] = df["high"].astype("float64")
    df["low"] = df["low"].astype("float64")
    df["close"] = df["close"].astype("float64")
    df["tick_volume"] = df["tick_volume"].astype("int64")

    # Deduplicate and sort strictly ascending by timestamp
    df = df.drop_duplicates(subset=["time"], keep="last")
    df = df.sort_values(by="time", ascending=True).reset_index(drop=True)

    return df[["time", "open", "high", "low", "close", "tick_volume"]]


def dataframe_to_parquet_bytes(df: pd.DataFrame, compression: str = "snappy") -> bytes:
    """
    Serializes DataFrame into compressed Apache Parquet binary bytes.
    """
    table = pa.Table.from_pandas(df, schema=CANDLE_ARROW_SCHEMA, preserve_index=False)
    buf = io.BytesIO()
    pq.write_table(
        table,
        buf,
        compression=compression,
        use_dictionary=True,
        write_statistics=True,
    )
    return buf.getvalue()


def parquet_bytes_to_dataframe(data: bytes) -> pd.DataFrame:
    """
    Reads Parquet bytes into a pandas DataFrame.
    """
    buf = io.BytesIO(data)
    table = pq.read_table(buf)
    return table.to_pandas()


def dataframe_to_compact_json_bytes(df: pd.DataFrame, limit: int | None = None) -> bytes:
    """
    Serializes candle DataFrame into compact JSON format (Array of Arrays)
    Format: [[time, open, high, low, close, volume], ...]
    """
    if limit is not None and limit > 0 and len(df) > limit:
        df = df.iloc[-limit:]

    records = df[["time", "open", "high", "low", "close", "tick_volume"]].values.tolist()
    # Format floats cleanly
    formatted_records = [
        [
            int(r[0]),
            round(float(r[1]), 5),
            round(float(r[2]), 5),
            round(float(r[3]), 5),
            round(float(r[4]), 5),
            int(r[5]),
        ]
        for r in records
    ]
    return json.dumps(formatted_records, separators=(",", ":")).encode("utf-8")


def merge_rates_with_parquet(
    existing_parquet_bytes: bytes | None,
    new_rates: list[dict[str, Any]],
) -> pd.DataFrame:
    """
    Merges newly fetched candle rates with existing Parquet dataset,
    ensuring idempotency, deduplication, and strictly ascending timestamp ordering.
    """
    new_df = rates_to_dataframe(new_rates)

    if not existing_parquet_bytes:
        return new_df

    try:
        existing_df = parquet_bytes_to_dataframe(existing_parquet_bytes)
        combined_df = pd.concat([existing_df, new_df], ignore_index=True)
        # Drop duplicates by time keeping the newest/last records
        combined_df = combined_df.drop_duplicates(subset=["time"], keep="last")
        combined_df = combined_df.sort_values(by="time", ascending=True).reset_index(drop=True)
        return combined_df
    except Exception as e:
        logger.error(f"Error parsing existing Parquet bytes during merge: {e}. Using new data.")
        return new_df
