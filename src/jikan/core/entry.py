from collections.abc import Sequence
from datetime import datetime, timedelta

from sqlmodel import Session, col, select

from jikan.lib.datetime import ensure_utc_aware, utc_now
from jikan.models import Entry, engine


class EntryAlreadyRunningError(Exception):
    pass


class EntryNotRunningError(Exception):
    pass


class EntryNotFoundError(Exception):
    pass


def get_entry(id: int) -> Entry:
    with Session(engine) as session:
        statement = select(Entry).where(Entry.id == id)
        entry = session.exec(statement).one_or_none()
        if entry is None:
            raise EntryNotFoundError
        return entry


def edit_entry(entry: Entry, title: str | None, description: str | None) -> Entry:
    with Session(engine) as session:
        db_entry = session.get(Entry, entry.id)
        if db_entry is None:
            raise EntryNotFoundError
        if title is not None:
            db_entry.title = title
        if description is not None:
            db_entry.description = description

        session.add(db_entry)
        session.commit()
        session.refresh(db_entry)
        return db_entry


def delete_entry(entry: Entry) -> None:
    with Session(engine) as session:
        db_entry = session.get(Entry, entry.id)
        if db_entry is None:
            raise EntryNotFoundError
        session.delete(db_entry)
        session.commit()


def start_time_entry(project_id: int | None, title: str, description: str) -> Entry:
    running_entry = get_running_entry()
    if running_entry != []:
        raise EntryAlreadyRunningError("Time entry is already running.")

    new_entry = Entry(
        project_id=project_id,
        title=title,
        description=description,
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
    now = utc_now()

    if ensure_utc_aware(entry.start_at) > now:
        raise RuntimeError(
            "Cannot stop: start time is in the future. Edit start_at to be <= now and retry."
        )

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
