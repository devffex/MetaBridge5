from datetime import UTC, datetime


def datetime_to_timestamp(dt: datetime) -> int:
    """
    Convert a datetime object to a Unix timestamp integer (seconds).
    If the datetime is naive, it's assumed to be local time.
    """
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=datetime.now().astimezone().tzinfo)
    return int(dt.timestamp())


def timestamp_to_datetime(ts: int) -> datetime:
    """
    Convert a Unix timestamp integer to a UTC-aware datetime object.
    """
    return datetime.fromtimestamp(ts, tz=UTC)
