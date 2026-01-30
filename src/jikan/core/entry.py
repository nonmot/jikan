from collections.abc import Sequence
from datetime import datetime, timedelta

from sqlalchemy.orm import selectinload
from sqlmodel import Session, col, select

from jikan.core.project import get_project
from jikan.core.tag import TagNotFoundError
from jikan.lib.datetime import ensure_utc_aware, utc_now
from jikan.lib.print import warn
from jikan.models import Entry, Tag, engine


class EntryAlreadyRunningError(Exception):
    pass


class EntryNotRunningError(Exception):
    pass


class EntryNotFoundError(Exception):
    pass


def get_entry(id: int) -> Entry:
    with Session(engine) as session:
        statement = select(Entry).options(selectinload(Entry.tags)).where(Entry.id == id)  # pyright: ignore[reportArgumentType]
        entry = session.exec(statement).one_or_none()
        if entry is None:
            raise EntryNotFoundError
        return entry


def edit_entry(
    entry: Entry,
    title: str | None = None,
    description: str | None = None,
    start_at: datetime | None = None,
    end_at: datetime | None = None,
    project_id: int | None = None,
    add_tags_id: list[int] | None = None,
    remove_tags_id: list[int] | None = None,
) -> Entry:
    with Session(engine) as session:
        db_entry = session.get(Entry, entry.id)
        if db_entry is None:
            raise EntryNotFoundError

        if title is not None:
            db_entry.title = title
        if description is not None:
            db_entry.description = description

        sa = db_entry.start_at if start_at is None else start_at
        ea = db_entry.end_at if end_at is None else end_at
        if ea is not None and sa > ea:
            raise ValueError("Start time must be before or equal to end time.")

        if start_at is not None:
            db_entry.start_at = start_at
        if end_at is not None:
            db_entry.end_at = end_at

        if project_id is not None:
            project = get_project(project_id)
            db_entry.project = project

        if add_tags_id:
            requested_ids = set(add_tags_id)
            existing_ids = {t.id for t in db_entry.tags}

            duplicated_ids = requested_ids & existing_ids
            if duplicated_ids:
                warn(f"Tag already added. ID={sorted(duplicated_ids)}")

            target_ids = requested_ids - existing_ids

            if target_ids:
                tags = session.exec(select(Tag).where(Tag.id.in_(target_ids))).all()

                found_ids = {t.id for t in tags}

                missing = target_ids - found_ids
                if missing:
                    raise TagNotFoundError(f"Tag not found. ID={sorted(missing)}")
                db_entry.tags.extend(tags)

        if remove_tags_id:
            requested_ids = set(remove_tags_id)
            existing_ids = {t.id for t in db_entry.tags}
            not_attached = requested_ids - existing_ids

            if not_attached:
                warn(f"Tag not attached. ID={sorted(not_attached)}")

            target_ids = requested_ids & existing_ids
            if target_ids:
                db_entry.tags = [t for t in db_entry.tags if t.id not in target_ids]

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
