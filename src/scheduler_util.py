"""Sleep until the next daily scrape time (before evening job applications)."""

from __future__ import annotations

import time
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo


def parse_hhmm(value: str) -> tuple[int, int]:
    parts = (value or "18:30").strip().split(":")
    hour = int(parts[0])
    minute = int(parts[1]) if len(parts) > 1 else 0
    return hour, minute


def seconds_until_next_run(*, time_str: str, tz_name: str) -> tuple[float, datetime]:
    tz = ZoneInfo(tz_name or "Europe/Berlin")
    hour, minute = parse_hhmm(time_str)
    now = datetime.now(tz)
    target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if target <= now:
        target += timedelta(days=1)
    return (target - now).total_seconds(), target
