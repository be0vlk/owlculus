"""
Utility functions used throughout the application.
"""

import base64
from datetime import datetime, timezone
from pathlib import Path


def get_project_root() -> Path:
    """Get the absolute path to the project root directory."""
    return Path(__file__).resolve().parent.parent.parent.parent.resolve()


def get_utc_now() -> datetime:
    """Returns the current UTC datetime rounded to the nearest second."""
    now = datetime.now(timezone.utc)
    return now.replace(microsecond=0)


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
