from app.pipeline.stream_sink import StreamParquetSink
from app.storage.local_backend import LocalStorageBackend


def test_stream_parquet_sink_buffer_and_close(tmp_path):
    storage = LocalStorageBackend(base_dir=str(tmp_path))
    sink = StreamParquetSink("EURUSD", "M1", storage, batch_rows=50)

    # Add 120 mock candles
    candles = [
        {
            "time": 1700000000 + (i * 60),
            "open": 1.1000 + (i * 0.0001),
            "high": 1.1010 + (i * 0.0001),
            "low": 1.0990 + (i * 0.0001),
            "close": 1.1005 + (i * 0.0001),
            "tick_volume": 100 + i,
            "spread": 2,
            "real_volume": 0,
        }
        for i in range(120)
    ]

    sink.add_candles(candles)
    summary = sink.close(write_recent_json=True)

    assert summary["uploaded"] is True
    assert summary["records_ingested"] == 120
    assert summary["chunks_flushed"] >= 2
    assert summary["symbol"] == "EURUSD"
    assert summary["timeframe"] == "M1"

    # Verify physical file existence in storage
    assert (tmp_path / "data" / "EURUSD" / "M1" / "history.parquet").exists()
    assert (tmp_path / "data" / "EURUSD" / "M1" / "recent.json").exists()


def test_stream_parquet_sink_abort_cleanup(tmp_path):
    storage = LocalStorageBackend(base_dir=str(tmp_path))
    sink = StreamParquetSink("GBPUSD", "M5", storage, batch_rows=10)

    candles = [
        {
            "time": 1700000000 + (i * 300),
            "open": 1.2500,
            "high": 1.2510,
            "low": 1.2490,
            "close": 1.2505,
            "tick_volume": 50,
            "spread": 1,
            "real_volume": 0,
        }
        for i in range(25)
    ]

    sink.add_candles(candles)
    sink.abort()

    # Nothing should be committed to storage
    assert not (tmp_path / "data" / "GBPUSD" / "M5" / "history.parquet").exists()
