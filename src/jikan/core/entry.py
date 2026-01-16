from collections.abc import Sequence
from datetime import datetime, timedelta

from sqlmodel import Session, col, select

from jikan.models import Entry, engine


class EntryAlreadyRunningError(Exception):
    pass


class EntryNotRunningError(Exception):
    pass


def start_time_entry(project_id: int, title: str, description: str) -> Entry:
    running_entry = get_running_entry()
    if running_entry != []:
        raise EntryAlreadyRunningError("Time entry is already running.")

    start_at = datetime.now()
    new_entry = Entry(
        project_id=project_id,
        title=title,
        description=description,
        start_at=start_at,
        created_at=start_at,
        updated_at=start_at,
    )
    with Session(engine) as session:
        session.add(new_entry)
        session.commit()
        session.refresh(new_entry)

    return new_entry


def stop_time_entry() -> Entry:
    running_entry = get_running_entry()

    if len(running_entry) == 0:
        raise EntryNotRunningError("No time entry running.")
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
    elasped_time = now - entry.start_at
    return elasped_time
