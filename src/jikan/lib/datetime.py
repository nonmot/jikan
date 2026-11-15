import datetime as _datetime
import os
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import typer

from jikan.config import load_config
from jikan.lib.print import warn

config = load_config()


def utc_now() -> _datetime.datetime:
    """Current UTC time, optionally fixed across CLI subprocesses for tests.

    JIKAN_TEST_NOW accepts an ISO-8601 timestamp with an explicit UTC offset,
    e.g. 2026-10-21T09:00:00+09:00. It is read on every call, not at import.
    """
    fixed = os.environ.get("JIKAN_TEST_NOW")
    if fixed is not None:
        try:
            value = _datetime.datetime.fromisoformat(fixed)
            if value.utcoffset() is None:
                raise ValueError("timezone offset is required")
        except ValueError as exc:
            raise ValueError("JIKAN_TEST_NOW must be ISO-8601 with a timezone offset") from exc
        return value.astimezone(_datetime.UTC)
    return _datetime.datetime.now(_datetime.UTC)


def ensure_utc_aware(dt: _datetime.datetime) -> _datetime.datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=_datetime.UTC)
    return dt.astimezone(_datetime.UTC)


def format_datetime(d: _datetime.datetime) -> str:
    d_str = d.strftime("%Y-%m-%d %H:%M:%S")
    return d_str


def convert_timezone(d: _datetime.datetime) -> _datetime.datetime:
    tz_str = config.timezone
    try:
        tz = ZoneInfo(tz_str)
    except (ValueError, ZoneInfoNotFoundError):
        warn("timezone config is invalid. Timezone UTC is used")
        tz = ZoneInfo("UTC")
    return ensure_utc_aware(d).astimezone(tz=tz)


def format_timedelta(d: _datetime.timedelta) -> str:
    total_sec = d.total_seconds()
    hours = total_sec // 3600
    remain = total_sec - (hours * 3600)
    minutes = remain // 60
    seconds = remain - (minutes * 60)
    return f"{int(hours):02}h {int(minutes):02}m {int(seconds):02}s"


def parse_dt(value: str) -> _datetime.datetime:
    """Parse local wall time in config.timezone, or an ISO time with an offset."""
    try:
        normalized = value.strip().replace("/", "-")
        if "T" not in normalized and " " not in normalized:
            raise ValueError("A time is required")
        parsed = _datetime.datetime.fromisoformat(normalized)
        if parsed.tzinfo is None:
            try:
                tz = ZoneInfo(config.timezone)
            except (ValueError, ZoneInfoNotFoundError):
                warn("timezone config is invalid. Timezone UTC is used")
                tz = ZoneInfo("UTC")
            parsed = parsed.replace(tzinfo=tz)
            # Reject nonexistent local times during a DST spring-forward gap.
            roundtrip = parsed.astimezone(_datetime.UTC).astimezone(tz)
            if roundtrip.replace(tzinfo=None) != parsed.replace(tzinfo=None):
                raise ValueError("Local time does not exist in configured timezone")
        return ensure_utc_aware(parsed)
    except ValueError as e:
        raise typer.BadParameter(
            "Invalid datetime. Use YYYY-MM-DD HH:MM[:SS] in the configured timezone "
            "or ISO-8601 with an offset (e.g. 2026-10-21T09:00:00+09:00). "
            "Legacy YYYY/MM/DD HH:MM:SS is also accepted."
        ) from e
