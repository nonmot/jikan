from typing import Sequence

from rich.console import Console
from rich.table import Table
from jikan.lib.print import success
from sqlmodel import Session, select, col

from jikan.models import Entry, engine
from datetime import datetime, timedelta


def start_time_entry(id: int, description: str) -> Entry:
    running_entry = get_running_entry()
    if running_entry != []:
        raise RuntimeError("Time entry is already running.")

    start_at = datetime.now()
    new_entry = Entry(
        project_id=id,
        description=description,
        start_at=start_at,
        created_at=start_at,
        updated_at=start_at,
    )
    with Session(engine) as session:
        session.add(new_entry)
        session.commit()
        session.refresh(new_entry)

    success(f"Time entry started at {new_entry.start_at}")
    return new_entry


def stop_time_entry() -> Entry:
    running_entry = get_running_entry()
    print(running_entry)

    if len(running_entry) == 0:
        raise RuntimeError("No time entry running.")
    elif len(running_entry) > 1:
        raise RuntimeError("Multiple time entries running")

    entry = running_entry[0]
    now = datetime.now()
    with Session(engine) as session:
        entry.end_at = now
        entry.updated_at = now
        session.add(entry)
        session.commit()
        session.refresh(entry)

    success(f"Time entry stopped at {entry.end_at}")
    return entry


def get_running_entry() -> Sequence[Entry]:
    with Session(engine) as session:
        statement = select(Entry).where(col(Entry.end_at).is_(None))
        entries = session.exec(statement).all()
        return entries


def list_time_entry() -> Sequence[Entry]:
    with Session(engine) as session:
        statement = select(Entry)
        time_entries = session.exec(statement).all()
        return time_entries

def running_time(entry: Entry) -> timedelta:
    now = datetime.now()
    running_time = now - entry.start_at
    return running_time
