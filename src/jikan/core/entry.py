from collections.abc import Sequence
from datetime import datetime, timedelta

from sqlalchemy.orm import selectinload
from sqlmodel import Session, col, select

from jikan.core.project import ProjectNotFoundError
from jikan.core.tag import TagNotFoundError
from jikan.db import recording_session_context, session_context
from jikan.lib.datetime import ensure_utc_aware, utc_now
from jikan.lib.print import warn
from jikan.models import Entry, Project, Tag


class EntryAlreadyRunningError(Exception):
    def __init__(self, message: str = "Time entry is already running.", entry: Entry | None = None):
        super().__init__(message)
        self.entry = entry


class EntryNotRunningError(Exception):
    pass


class EntryNotFoundError(Exception):
    pass


def get_entry(id: int) -> Entry:
    with session_context() as session:
        statement = (
            select(Entry)
            .options(selectinload(Entry.tags), selectinload(Entry.project))  # pyright: ignore[reportArgumentType]
            .where(Entry.id == id)
        )
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
    *,
    project_name: str | None = None,
    tag_names: Sequence[str] | None = None,
    remove_tag_names: Sequence[str] | None = None,
) -> Entry:
    """Validate all edits before mutation, then persist them in one transaction.

    Numeric names take priority over legacy numeric --project/--remove-tag
    values. Explicit ID options remain unambiguous.
    """
    with recording_session_context() as session:
        db_entry = session.get(Entry, entry.id)
        if db_entry is None:
            raise EntryNotFoundError

        sa = db_entry.start_at if start_at is None else start_at
        ea = db_entry.end_at if end_at is None else end_at
        if ea is not None and ensure_utc_aware(sa) > ensure_utc_aware(ea):
            raise ValueError("Start time must be before or equal to end time. Retry --start/--end.")

        if project_name is not None and project_id is None and project_name.isdecimal():
            named = session.exec(select(Project).where(Project.name == project_name)).one_or_none()
            if named is None:
                project_id, project_name = int(project_name), None
        project, added = _resolve_classification(session, project_id, project_name, tag_names)
        removed = []
        for name in dict.fromkeys(remove_tag_names or ()):
            named = session.exec(select(Tag).where(Tag.name == name)).one_or_none()
            if named is None and name.isdecimal():
                named = session.get(Tag, int(name))
            if named is None:
                # Reuse the shared resolver's error and recovery guidance.
                _resolve_classification(session, None, None, [name])
            removed.append(named)

        for tag_id in dict.fromkeys(add_tags_id or ()):
            tag = session.get(Tag, tag_id)
            if tag is None:
                raise TagNotFoundError(
                    f"Tag not found. ID={tag_id}. Check `jikan tag list` "
                    "or register with `jikan tag add --name NAME`."
                )
            added.append(tag)
        for tag_id in dict.fromkeys(remove_tags_id or ()):
            tag = session.get(Tag, tag_id)
            if tag is None:
                raise TagNotFoundError(
                    f"Tag not found. ID={tag_id}. Check `jikan tag list` "
                    "or register with `jikan tag add --name NAME`."
                )
            removed.append(tag)
        remove_ids = {tag.id for tag in removed}
        # Existing but unattached tags are valid classifications: removal is a no-op.
        existing_ids = {tag.id for tag in db_entry.tags}
        duplicate_ids = existing_ids & {tag.id for tag in added}
        if duplicate_ids:
            warn(f"Tag already added. ID={sorted(duplicate_ids)}")
        if remove_ids - existing_ids:
            warn(f"Tag not attached. ID={sorted(remove_ids - existing_ids)}")
        tags = {tag.id: tag for tag in [*db_entry.tags, *added]}
        final_tags = [tag for tag_id, tag in tags.items() if tag_id not in remove_ids]
        now = utc_now()

        if title is not None:
            db_entry.title = title
        if description is not None:
            db_entry.description = description
        if start_at is not None:
            db_entry.start_at = ensure_utc_aware(start_at)
        if end_at is not None:
            db_entry.end_at = ensure_utc_aware(end_at)
        if project_id is not None or project_name is not None:
            db_entry.project = project
        db_entry.tags = final_tags
        db_entry.updated_at = now
        session.add(db_entry)
        session.commit()
        session.refresh(db_entry)
        return _load_relations(db_entry)


def delete_entry(entry: Entry) -> None:
    with session_context() as session:
        db_entry = session.get(Entry, entry.id)
        if db_entry is None:
            raise EntryNotFoundError
        session.delete(db_entry)
        session.commit()


def _load_relations(entry: Entry) -> Entry:
    # Access while attached so every returned entry remains usable after close.
    _ = entry.project, entry.tags
    return entry


def _running_entries(session: Session) -> Sequence[Entry]:
    return session.exec(
        select(Entry)
        .options(selectinload(Entry.project), selectinload(Entry.tags))
        .where(col(Entry.end_at).is_(None))
        .order_by(Entry.id)
    ).all()


def _resolve_classification(
    session: Session,
    project_id: int | None,
    project_name: str | None,
    tag_names: Sequence[str] | None,
) -> tuple[Project | None, list[Tag]]:
    if project_id is not None and project_name is not None:
        raise ValueError("Use either --project NAME or --project-id ID (--id), not both.")
    project = None
    if project_name is not None:
        project = session.exec(select(Project).where(Project.name == project_name)).one_or_none()
        if project is None:
            raise ProjectNotFoundError(
                f"Project not found: {project_name!r}. "
                "Check `jikan project list` or register with `jikan project add --name NAME`."
            )
    elif project_id is not None:
        project = session.get(Project, project_id)
        if project is None:
            raise ProjectNotFoundError(
                f"Project not found. ID={project_id}. Check `jikan project list` "
                "or register with `jikan project add --name NAME`."
            )
    tags = []
    for name in dict.fromkeys(tag_names or ()):
        tag = session.exec(select(Tag).where(Tag.name == name)).one_or_none()
        if tag is None:
            raise TagNotFoundError(
                f"Tag not found: {name!r}. "
                "Check `jikan tag list` or register with `jikan tag add --name NAME`."
            )
        tags.append(tag)
    return project, tags


def _new_entry(
    session: Session,
    title: str,
    description: str,
    project: Project | None,
    tags: list[Tag],
    now: datetime,
) -> Entry:
    entry = Entry(
        title=title,
        description=description,
        project=project,
        tags=tags,
        start_at=now,
        created_at=now,
        updated_at=now,
    )
    session.add(entry)
    return entry


def start_time_entry(
    project_id: int | None,
    title: str,
    description: str,
    *,
    project_name: str | None = None,
    tag_names: Sequence[str] | None = None,
) -> Entry:
    with recording_session_context() as session:
        running = _running_entries(session)
        if len(running) > 1:
            raise RuntimeError(
                "Multiple time entries running. Inspect `jikan list --all` and edit."
            )
        if running:
            raise EntryAlreadyRunningError(entry=running[0])
        project, tags = _resolve_classification(session, project_id, project_name, tag_names)
        entry = _new_entry(session, title, description, project, tags, utc_now())
        session.commit()
        session.refresh(entry)
        return _load_relations(entry)


def _stop_entry(entry: Entry, now: datetime) -> None:
    if ensure_utc_aware(entry.start_at) > ensure_utc_aware(now):
        raise RuntimeError(
            "Cannot stop: start time is in the future. Edit start_at to be <= now and retry."
        )
    entry.end_at = now
    entry.updated_at = now


def stop_time_entry() -> Entry:
    with recording_session_context() as session:
        running = _running_entries(session)
        if not running:
            raise EntryNotRunningError("No time entry running. Check `jikan status`.")
        if len(running) > 1:
            raise RuntimeError("Multiple time entries running")
        entry = running[0]
        _stop_entry(entry, utc_now())
        session.commit()
        session.refresh(entry)
        return _load_relations(entry)


def switch_time_entry(
    project_id: int | None,
    title: str,
    description: str,
    *,
    project_name: str | None = None,
    tag_names: Sequence[str] | None = None,
) -> tuple[Entry | None, Entry]:
    """Atomically return (stopped entry or None, started entry)."""
    with recording_session_context() as session:
        project, tags = _resolve_classification(session, project_id, project_name, tag_names)
        running = _running_entries(session)
        if len(running) > 1:
            raise RuntimeError("Multiple time entries running")
        now = utc_now()
        stopped = running[0] if running else None
        if stopped is not None:
            _stop_entry(stopped, now)
            session.flush()
        started = _new_entry(session, title, description, project, tags, now)
        session.commit()
        if stopped is not None:
            session.refresh(stopped)
            _load_relations(stopped)
        session.refresh(started)
        return stopped, _load_relations(started)


def get_running_entry() -> Sequence[Entry]:
    with session_context() as session:
        statement = (
            select(Entry)
            .options(selectinload(Entry.project), selectinload(Entry.tags))  # pyright: ignore[reportArgumentType]
            .where(col(Entry.end_at).is_(None))
        )
        entries = session.exec(statement).all()
        return entries


def list_time_entry() -> Sequence[Entry]:
    with session_context() as session:
        statement = select(Entry)
        time_entries = session.exec(statement).all()
        return time_entries


def running_time(entry: Entry) -> timedelta:
    now = utc_now()
    elapsed_time = now - ensure_utc_aware(entry.start_at)
    return elapsed_time
