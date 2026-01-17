from datetime import datetime, timedelta

def format_datetime(d: datetime) -> str:
    d_str = d.strftime("%Y-%m-%d %H:%M:%S")
    return d_str

def format_timedelta(d: timedelta) -> str:
    total_sec = d.total_seconds()
    hours = total_sec // 3600
    remain = total_sec - (hours * 3600)
    minutes = remain // 60
    seconds = remain - (minutes * 60)
    return '{:02}:{:02}:{:02}'.format(int(hours), int(minutes), int(seconds))
