import datetime as _datetime

import typer


def utc_now() -> _datetime.datetime:
    return _datetime.datetime.now(_datetime.UTC)


def ensure_utc_aware(dt: _datetime.datetime) -> _datetime.datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=_datetime.UTC)
    return dt.astimezone(_datetime.UTC)


def format_datetime(d: _datetime.datetime) -> str:
    d_str = d.strftime("%Y-%m-%d %H:%M:%S")
    return d_str


def format_timedelta(d: _datetime.timedelta) -> str:
    total_sec = d.total_seconds()
    hours = total_sec // 3600
    remain = total_sec - (hours * 3600)
    minutes = remain // 60
    seconds = remain - (minutes * 60)
    return f"{int(hours):02}h {int(minutes):02}m {int(seconds):02}s"


def parse_dt(value: str) -> _datetime.datetime:
    fmt = "%Y/%m/%d %H:%M:%S"
    try:
        parse_dt = _datetime.datetime.strptime(value, fmt)
        return ensure_utc_aware(parse_dt)
    except ValueError as e:
        raise typer.BadParameter("Invalid datetime. Use format like YYYY/MM/DD HH:MM:SS") from e
