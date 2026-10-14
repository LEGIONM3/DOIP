"""Timezone-aware datetime utilities for DOIP.

Eliminates Python 3.12+ `datetime.utcnow()` deprecation warnings and enforces
consistent UTC standards across the platform.
"""

from __future__ import annotations

import datetime


def utc_now() -> datetime.datetime:
    """Return the current timezone-aware UTC datetime."""
    return datetime.datetime.now(datetime.timezone.utc)


def utc_iso() -> str:
    """Return the current timezone-aware UTC datetime formatted as an ISO 8601 string."""
    return utc_now().isoformat()


def utc_date_str(fmt: str = "%Y-%m-%d") -> str:
    """Return current UTC date formatted by format string."""
    return utc_now().strftime(fmt)


def parse_utc_iso(iso_str: str) -> datetime.datetime:
    """Parse an ISO 8601 string into a timezone-aware UTC datetime."""
    dt = datetime.datetime.fromisoformat(iso_str)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=datetime.timezone.utc)
    return dt
