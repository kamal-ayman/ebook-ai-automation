from __future__ import annotations

from datetime import datetime


def stamp(message: str) -> str:
    """Add a compact timestamp to log messages."""

    return f"[{datetime.now().strftime('%H:%M:%S')}] {message}"
