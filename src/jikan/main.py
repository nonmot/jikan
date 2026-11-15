from typing import Annotated

import typer
from rich import print
from rich.console import Console
from typer import Typer

from jikan.commands import project, tag
from jikan.commands.history import export_history, list_history, report_history
from jikan.commands.timer import timer
from jikan.completion import complete_projects, complete_tags
from jikan.core.entry import (
    EntryAlreadyRunningError,
    EntryNotFoundError,
    EntryNotRunningError,
    delete_entry,
    edit_entry,
    get_entry,
    get_running_entry,
    running_time,
    start_time_entry,
    stop_time_entry,
    switch_time_entry,
)
from jikan.core.project import ProjectNotFoundError
from jikan.db import SQLITE_PATH, create_db_and_tables
from jikan.lib.datetime import (
    convert_timezone,
    ensure_utc_aware,
    format_datetime,
    format_timedelta,
    parse_dt,
)
from jikan.lib.print import error, success
from jikan.models import Entry

console = Console()

app = Typer()


@app.command()
def init():
    create_db_and_tables()
    success(f"Database initialized: {SQLITE_PATH}")
    print("Next: jikan project add --name NAME; jikan tag add --name NAME")
    print('Start: jikan start --title "Your task"')


app.add_typer(project.app, name="project")
app.add_typer(tag.app, name="tag")


def _print_recording(entry: Entry) -> None:
    # User supplied titles/names are literal text, not Rich markup.
    console.print(f"ID: {entry.id}", markup=False)
    console.print(f"Title: {entry.title or ''}", markup=False)
    console.print(f"Description: {entry.description or ''}", markup=False)
    console.print(f"Start at: {format_datetime(convert_timezone(entry.start_at))}", markup=False)
    console.print(f"Project: {entry.project.name if entry.project else 'Unassigned'}", markup=False)
    console.print(f"Tags: {', '.join(t.name for t in entry.tags) or 'Unassigned'}", markup=False)


def _print_stopped(entry: Entry) -> None:
    if entry.end_at is None:
        raise RuntimeError("Entry end_at must be set after stopping")
    success(f"Time entry stopped at {format_datetime(convert_timezone(entry.end_at))}")
    console.print(f"Stopped #{entry.id}: {entry.title or ''}", markup=False)
    duration = ensure_utc_aware(entry.end_at) - ensure_utc_aware(entry.start_at)
    console.print(f"Duration: {format_timedelta(duration)}", markup=False)


@app.command()
def start(
    id: Annotated[
        int | None, typer.Option("--project-id", "--id", help="Project ID (compatibility option)")
    ] = None,
    title: Annotated[str, typer.Option("--title", "-t", help="Title of time entry")] = "",
    description: Annotated[
        str, typer.Option("--description", "-d", help="Description of time entry")
    ] = "",
    project: Annotated[
        str | None, typer.Option(help="Project name", autocompletion=complete_projects)
    ] = None,
    tag: Annotated[
        list[str] | None,
        typer.Option("--tag", help="Tag name; repeat for more", autocompletion=complete_tags),
    ] = None,
):
    try:
        new_entry = start_time_entry(id, title, description, project_name=project, tag_names=tag)
        success(f"Time entry started at {format_datetime(convert_timezone(new_entry.start_at))}")
        console.print(f"Started #{new_entry.id}", markup=False)
        _print_recording(new_entry)
    except EntryAlreadyRunningError as e:
        error("Time entry is already running")
        if e.entry is not None:
            console.print(f"Running #{e.entry.id}", markup=False)
            _print_recording(e.entry)
        console.print('Next: jikan switch --title "Your next task"; or jikan stop', markup=False)
        raise typer.Exit(code=1) from e
    except Exception as e:
        error(f"Failed to start. {e}")
        raise typer.Exit(code=1) from e


@app.command()
def stop():
    try:
        _print_stopped(stop_time_entry())
    except EntryNotRunningError as e:
        error("No time entry running. Check `jikan status`.")
        raise typer.Exit(code=1) from e
    except Exception as e:
        error(f"Failed to stop. {e}")
        raise typer.Exit(code=1) from e


@app.command()
def switch(
    id: Annotated[
        int | None, typer.Option("--project-id", "--id", help="Project ID (compatibility option)")
    ] = None,
    title: Annotated[str, typer.Option("--title", "-t", help="Title of time entry")] = "",
    description: Annotated[
        str, typer.Option("--description", "-d", help="Description of time entry")
    ] = "",
    project: Annotated[
        str | None, typer.Option(help="Project name", autocompletion=complete_projects)
    ] = None,
    tag: Annotated[
        list[str] | None,
        typer.Option("--tag", help="Tag name; repeat for more", autocompletion=complete_tags),
    ] = None,
):
    try:
        stopped, started = switch_time_entry(
            id, title, description, project_name=project, tag_names=tag
        )
        if stopped is None:
            console.print("No time entry running; starting a new entry.", markup=False)
        else:
            _print_stopped(stopped)
            _print_recording(stopped)
        success(f"Time entry started at {format_datetime(convert_timezone(started.start_at))}")
        console.print(f"Started #{started.id}", markup=False)
        _print_recording(started)
    except Exception as e:
        error(f"Failed to switch. {e}")
        raise typer.Exit(code=1) from e


@app.command()
def status():
    try:
        running_entry = get_running_entry()
        if len(running_entry) == 0:
            console.print('No time entry running. Start: jikan start --title "Your task"')
            return
        if len(running_entry) > 1:
            raise RuntimeError("Multiple time entries running")
        entry = running_entry[0]
        console.print(f"Running #{entry.id}", markup=False)
        _print_recording(entry)
        console.print(f"Time entry running: {format_timedelta(running_time(entry))}", markup=False)
    except Exception as e:
        error(f"Failed to get status. {e}")
        raise typer.Exit(code=1) from e


app.command("timer")(timer)
app.command("list")(list_history)
app.command("report")(report_history)
app.command("export")(export_history)


@app.command()
def edit(
    id: Annotated[int, typer.Argument(help="ID of time entry to be edited")],
    title: Annotated[str | None, typer.Option("--title", "-t", help="Title of time entry")] = None,
    description: Annotated[
        str | None, typer.Option("--description", "-d", help="Description of time entry")
    ] = None,
    start: Annotated[str | None, typer.Option(help="Start time of time entry")] = None,
    end: Annotated[str | None, typer.Option(help="End time of time entry")] = None,
    project: Annotated[
        str | None, typer.Option(help="Project name", autocompletion=complete_projects)
    ] = None,
    project_id: Annotated[
        int | None, typer.Option("--project-id", help="Project ID (compatibility option)")
    ] = None,
    tag: Annotated[
        list[str] | None,
        typer.Option(
            "--tag", help="Add tag by name; repeat for more", autocompletion=complete_tags
        ),
    ] = None,
    add_tag: Annotated[
        list[int] | None, typer.Option("--add-tag", help="Add tag by ID (compatibility option)")
    ] = None,
    remove_tag: Annotated[
        list[str] | None,
        typer.Option("--remove-tag", help="Remove tag by name", autocompletion=complete_tags),
    ] = None,
    remove_tag_id: Annotated[
        list[int] | None,
        typer.Option("--remove-tag-id", help="Remove tag by ID (compatibility option)"),
    ] = None,
):
    if (
        title is None
        and description is None
        and start is None
        and end is None
        and project is None
        and project_id is None
        and tag is None
        and remove_tag_id is None
        and add_tag is None
        and remove_tag is None
    ):
        error(
            "Specify a change: --title, --description, --start, --end, "
            "--project, --tag or --remove-tag"
        )
        raise typer.Exit(code=1) from None

    start_at = None
    if start is not None:
        try:
            start_at = parse_dt(start)
        except typer.BadParameter as e:
            error(f"Invalid --start value: {e}")
            raise typer.Exit(code=1) from e

    end_at = None
    if end is not None:
        try:
            end_at = parse_dt(end)
        except typer.BadParameter as e:
            error(f"Invalid --end value: {e}")
            raise typer.Exit(code=1) from e

    try:
        entry = get_entry(id)
        updated = edit_entry(
            entry,
            title,
            description,
            start_at,
            end_at,
            project_id,
            add_tag,
            remove_tag_id,
            project_name=project,
            tag_names=tag,
            remove_tag_names=remove_tag,
        )
        success("Entry edited")
        console.print(f"Updated #{updated.id}", markup=False)
        _print_recording(updated)
        if updated.end_at is None:
            console.print("End at: Still running", markup=False)
            duration = running_time(updated)
        else:
            console.print(
                f"End at: {format_datetime(convert_timezone(updated.end_at))}", markup=False
            )
            duration = ensure_utc_aware(updated.end_at) - ensure_utc_aware(updated.start_at)
        console.print(f"Duration: {format_timedelta(duration)}", markup=False)
    except EntryNotFoundError as e:
        error("Entry not found")
        raise typer.Exit(code=1) from e
    except ProjectNotFoundError as e:
        error(f"Project not found: {e}")
        raise typer.Exit(code=1) from e
    except Exception as e:
        error(f"Failed to edit entry: {e}")
        raise typer.Exit(code=1) from e


@app.command()
def delete(id: Annotated[int, typer.Argument(help="ID of entry to be deleted")]):
    try:
        entry = get_entry(id)
        print(str(entry))
        _ = typer.confirm("Are you sure you want to delete it?", abort=True)
        delete_entry(entry)
        success("Entry deleted")
    except typer.Abort as e:
        raise typer.Exit(code=1) from e
    except EntryNotFoundError as e:
        error("Entry not found")
        raise typer.Exit(code=1) from e
    except Exception as e:
        error("Failed to delete entry")
        raise typer.Exit(code=1) from e


@app.command()
def view(id: Annotated[int, typer.Argument(help="ID of entry to be viewed")]):
    try:
        entry = get_entry(id)

        _print_recording(entry)
        duration = (
            format_timedelta(ensure_utc_aware(entry.end_at) - ensure_utc_aware(entry.start_at))
            if entry.end_at is not None
            else ""
        )
        console.print(f"Duration: {duration}", markup=False)
        if entry.end_at is not None:
            end_at_str = format_datetime(convert_timezone(entry.end_at))
        else:
            end_at_str = "Still running"
        console.print(f"End at: {end_at_str}", markup=False)
    except EntryNotFoundError as e:
        error("Entry not found")
        raise typer.Exit(code=1) from e
