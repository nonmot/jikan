"""History command callbacks, ready for top-level Typer registration.

Replace main's existing callbacks with:
    app.command("list")(list_history)
    app.command("report")(report_history)
    app.command("export")(export_history)
Alternatively, ``app`` exposes the same three commands for standalone use.
"""

import csv
import sys
from datetime import timedelta
from typing import Annotated

import typer

from jikan.completion import complete_projects, complete_tags
from jikan.core.query import HistoryQueryError, HistoryResult, query_history
from jikan.lib.datetime import format_timedelta

app = typer.Typer(help="Inspect history by entry start date in the configured timezone.")

Today = Annotated[bool, typer.Option("--today", help="Select today (the default).")]
AllDates = Annotated[bool, typer.Option("--all", help="Select all dates.")]
FromDate = Annotated[str | None, typer.Option("--from", help="First start date, YYYY-MM-DD.")]
ToDate = Annotated[str | None, typer.Option("--to", help="Last start date, inclusive, YYYY-MM-DD.")]
ProjectName = Annotated[
    str | None,
    typer.Option("--project", help="Exact project name.", autocompletion=complete_projects),
]
TagNames = Annotated[
    list[str] | None,
    typer.Option(
        "--tag",
        help="Exact tag name; repeat to require every tag (AND).",
        autocompletion=complete_tags,
    ),
]


def _query(today, all_dates, from_date, to_date, project, tags) -> HistoryResult:
    try:
        return query_history(
            today=today,
            all_dates=all_dates,
            from_date=from_date,
            to_date=to_date,
            project=project,
            tags=tags or (),
        )
    except HistoryQueryError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1) from exc


def _empty(*, err: bool = False) -> None:
    typer.echo("No entries match these conditions. Try --all or another date range.", err=err)


@app.command("list")
def list_history(
    today: Today = False,
    all_dates: AllDates = False,
    from_date: FromDate = None,
    to_date: ToDate = None,
    project: ProjectName = None,
    tag: TagNames = None,
) -> None:
    """List entries (today by default), including elapsed time for Running entries."""
    result = _query(today, all_dates, from_date, to_date, project, tag)
    typer.echo(result.describe())
    typer.echo("Date\tID\tStatus\tDuration\tTitle\tProject\tTags")
    for row in result.rows:
        typer.echo(
            "\t".join(
                (
                    row.start_at.isoformat(),
                    str(row.id),
                    "Running" if row.end_at is None else "Done",
                    format_timedelta(row.duration),
                    row.title,
                    row.project if row.project is not None else "Unassigned",
                    ", ".join(row.tags) or "Unassigned",
                )
            )
        )
    if not result.rows:
        _empty()
    typer.echo(f"Total: {format_timedelta(result.total)}")


def _breakdown(totals: dict[str | None, timedelta]) -> None:
    for name in sorted(totals, key=lambda name: (name is None, name or "")):
        typer.echo(
            f"  {name if name is not None else 'Unassigned'}  {format_timedelta(totals[name])}"
        )


@app.command("report")
def report_history(
    today: Today = False,
    all_dates: AllDates = False,
    from_date: FromDate = None,
    to_date: ToDate = None,
    project: ProjectName = None,
    tag: TagNames = None,
) -> None:
    """Report full entry durations with exclusive project and overlapping tag totals."""
    result = _query(today, all_dates, from_date, to_date, project, tag)
    typer.echo(result.describe())
    if not result.rows:
        _empty()
    typer.echo(f"Total: {format_timedelta(result.total)}")
    typer.echo("By project (exclusive; adds to Total)")
    _breakdown(result.breakdown())
    typer.echo("By tag (overlapping; may not add to Total; each tag receives full duration)")
    _breakdown(result.breakdown(by_tag=True))


def _csv_duration(duration: timedelta) -> str:
    hours, remainder = divmod(int(duration.total_seconds()), 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours:02}:{minutes:02}:{seconds:02}"


@app.command("export")
def export_history(
    today: Today = False,
    all_dates: AllDates = False,
    from_date: FromDate = None,
    to_date: ToDate = None,
    project: ProjectName = None,
    tag: TagNames = None,
    format: Annotated[str, typer.Option("--format", help="Output format (csv only). ")] = "csv",
) -> None:
    """Write CSV only to stdout; conditions and empty-result notices go to stderr."""
    if format != "csv":
        typer.echo("Error: Unsupported --format. Use --format csv.", err=True)
        raise typer.Exit(code=1)
    result = _query(today, all_dates, from_date, to_date, project, tag)
    typer.echo(result.describe(), err=True)
    if not result.rows:
        _empty(err=True)
    writer = csv.writer(sys.stdout, lineterminator="\r\n")
    writer.writerow(("id", "start_at", "end_at", "duration", "title", "project", "tags"))
    for row in result.rows:
        writer.writerow(
            (
                row.id,
                row.start_at.isoformat(),
                row.end_at.isoformat() if row.end_at else "",
                _csv_duration(row.duration),
                row.title,
                row.project or "",
                ",".join(row.tags),
            )
        )
