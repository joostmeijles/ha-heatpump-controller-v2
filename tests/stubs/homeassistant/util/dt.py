"""Stub for homeassistant.util.dt."""

from datetime import datetime, timezone


def utcnow() -> datetime:
    """Return current UTC time."""
    return datetime.now(tz=timezone.utc)
