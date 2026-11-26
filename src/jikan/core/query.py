"""Shared, read-only history queries.

Periods select by start_at in the configured timezone, not by overlap. An
included entry contributes its entire duration. Naive persisted datetimes are
UTC (SQLite drops tzinfo); aware values are converted to UTC before arithmetic.
Repeated tags use AND semantics. No filter creates or changes classifications.
"""

import sys
from collections.abc import Sequence
from contextlib import redirect_stdout
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy.orm import selectinload
from sqlmodel import select

from jikan.config import load_config
from jikan.db import session_context
from jikan.lib import datetime as clock
from jikan.models import Entry, Project, Tag


class HistoryQueryError(ValueError):
    """Invalid history filters, configuration, or persisted time range."""


@dataclass(frozen=True)
class HistoryRow:
    id: int
    start_at: datetime
    end_at: datetime | None
    duration: timedelta
    title: str
    project: str | None
    tags: tuple[str, ...]


@dataclass(frozen=True)
class HistoryResult:
    rows: tuple[HistoryRow, ...]
    timezone: str
    from_date: date | None
    to_date: date | None
    project: str | None
    tags: tuple[str, ...]
    as_of: datetime

    @property
    def total(self) -> timedelta:
        return sum((row.duration for row in self.rows), timedelta())

    def breakdown(self, *, by_tag: bool = False) -> dict[str | None, timedelta]:
        """None denotes unassigned; every attached tag receives full duration."""
        totals: dict[str | None, timedelta] = {}
        for row in self.rows:
            names = (row.tags or (None,)) if by_tag else (row.project,)
            for name in names:
                totals[name] = totals.get(name, timedelta()) + row.duration
        return totals

    def describe(self) -> str:
        period = (
            "All dates"
            if self.from_date is None and self.to_date is None
            else (
                f"{self.from_date or 'unbounded'} to {self.to_date or 'unbounded'} "
                "(inclusive dates)"
            )
        )
        return (
            f"Period: {period} ({self.timezone})\n"
            "Selection: start_at in period; entire duration, no clipping.\n"
            f"Project: {self.project if self.project is not None else 'All projects'}\n"
            f"Tags (all required / AND): {', '.join(self.tags) if self.tags else 'All tags'}"
        )


def _date(value: str | None, option: str) -> date | None:
    if value is None:
        return None
    try:
        parsed = date.fromisoformat(value)
        if parsed.isoformat() != value:
            raise ValueError
        return parsed
    except ValueError as exc:
        raise HistoryQueryError(
            f"Invalid {option} date {value!r}. Use YYYY-MM-DD, e.g. {option} 2026-10-21."
        ) from exc


def query_history(
    *,
    today: bool = False,
    all_dates: bool = False,
    from_date: str | None = None,
    to_date: str | None = None,
    project: str | None = None,
    tags: Sequence[str] = (),
) -> HistoryResult:
    """Return detached snapshots using one clock reading for all running rows.

    No period options means today for all history commands. A single --from or
    --to is open-ended. Explicit periods cannot be combined with today/all.
    """
    if (today and all_dates) or ((today or all_dates) and (from_date or to_date)):
        raise HistoryQueryError(
            "Use only one period mode: --today, --all, or --from/--to YYYY-MM-DD."
        )
    first, last = _date(from_date, "--from"), _date(to_date, "--to")
    if first is not None and last is not None and first > last:
        raise HistoryQueryError("--from must be on or before --to. Check the date range.")

    # Existing config loader may print warnings; keep even those off CSV stdout.
    with redirect_stdout(sys.stderr):
        config = load_config()
    try:
        tz = ZoneInfo(config.timezone)
    except (ValueError, ZoneInfoNotFoundError) as exc:
        raise HistoryQueryError(
            f"Invalid timezone {config.timezone!r}. Set timezone to e.g. Asia/Tokyo in config.toml."
        ) from exc
    now = clock.ensure_utc_aware(clock.utc_now())
    if not all_dates and first is None and last is None:
        first = last = now.astimezone(tz).date()
    try:
        lower = (
            clock.ensure_utc_aware(datetime.combine(first, time.min, tz))
            if first is not None
            else None
        )
        upper = (
            clock.ensure_utc_aware(datetime.combine(last + timedelta(days=1), time.min, tz))
            if last is not None
            else None
        )
    except (OverflowError, ValueError) as exc:
        raise HistoryQueryError(
            "Date range exceeds supported dates. Choose a smaller range."
        ) from exc

    names = tuple(dict.fromkeys(tags))
    rows = []
    with session_context() as session:
        statement = select(Entry).options(selectinload(Entry.project), selectinload(Entry.tags))
        if project is not None:
            found = session.exec(select(Project).where(Project.name == project)).one_or_none()
            if found is None:
                raise HistoryQueryError(
                    f"Project {project!r} not found. Use jikan project list or jikan project add."
                )
            statement = statement.where(Entry.project_id == found.id)
        for name in names:
            tag = session.exec(select(Tag).where(Tag.name == name)).one_or_none()
            if tag is None:
                raise HistoryQueryError(
                    f"Tag {name!r} not found. Use jikan tag list or jikan tag add."
                )
            statement = statement.where(Entry.tags.any(Tag.id == tag.id))

        # Normalize before comparing: SQLite returns naive UTC, while injected
        # sessions may return aware values. SQL text comparisons cannot ensure
        # that the two representations obey the same boundary semantics.
        for entry in session.exec(statement).all():
            start = clock.ensure_utc_aware(entry.start_at)
            if (lower is not None and start < lower) or (upper is not None and start >= upper):
                continue
            end = clock.ensure_utc_aware(entry.end_at) if entry.end_at is not None else None
            duration = (end if end is not None else now) - start
            if duration < timedelta():
                raise HistoryQueryError(
                    f"Entry #{entry.id} has a negative duration. Use jikan edit {entry.id} "
                    "to correct its start/end time."
                )
            assert entry.id is not None
            rows.append(
                HistoryRow(
                    id=entry.id,
                    start_at=start.astimezone(tz),
                    end_at=end.astimezone(tz) if end is not None else None,
                    duration=duration,
                    title=entry.title or "",
                    project=entry.project.name if entry.project is not None else None,
                    tags=tuple(sorted(tag.name for tag in entry.tags)),
                )
            )
    rows.sort(key=lambda row: (clock.ensure_utc_aware(row.start_at), row.id))
    return HistoryResult(tuple(rows), tz.key, first, last, project, names, now.astimezone(tz))
