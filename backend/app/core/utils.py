"""
Utility functions used throughout the application.
"""

import base64
from datetime import UTC, datetime, timezone
from pathlib import Path
from typing import Any


def get_project_root() -> Path:
    """Get the absolute path to the project root directory."""
    return Path(__file__).resolve().parent.parent.parent.parent.resolve()


def get_utc_now() -> datetime:
    """Returns the current UTC datetime rounded to the nearest second."""
    now = datetime.now(timezone.utc)
    return now.replace(microsecond=0)


def iso_utc(value: datetime) -> str:
    """ISO 8601 in UTC, treating naive datetimes as UTC."""
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).isoformat()


def optional_iso_utc(value: datetime | None) -> str | None:
    return iso_utc(value) if value is not None else None


def json_default(value: Any) -> str:
    """`json.dumps` default that writes datetimes as UTC ISO 8601."""
    if isinstance(value, datetime):
        return iso_utc(value)
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


def b64_encode(plain_str: str | None) -> str | None:
    """Encode content to base64"""
    if plain_str is None:
        return None
    return base64.b64encode(plain_str.encode("utf-8")).decode("utf-8")


def b64_decode(encoded_str: str | None) -> str | None:
    """Decode base64 content"""
    if encoded_str is None:
        return None
    return base64.b64decode(encoded_str.encode("utf-8")).decode("utf-8")
