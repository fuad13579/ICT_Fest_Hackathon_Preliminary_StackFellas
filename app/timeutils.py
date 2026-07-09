"""Helpers for parsing input datetimes and rendering UTC responses."""
from datetime import datetime, timezone


def utcnow() -> datetime:
    """Return the current UTC time as a naive datetime for SQLite storage."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def parse_input_datetime(value: str) -> datetime:
    """Parse an ISO 8601 datetime into a naive UTC datetime for storage.

    Inputs that carry a UTC offset are normalized to UTC; naive inputs are
    treated as UTC as-is.
    """
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


def iso_utc(dt: datetime) -> str:
    """Render a stored (naive UTC) datetime with an explicit UTC designator."""
    return dt.replace(tzinfo=timezone.utc).isoformat().replace("+00:00", "Z")
