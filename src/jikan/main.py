from typing import Annotated

import typer
from rich import print
from rich.console import Console
from rich.table import Table
from typer import Typer

from jikan.commands import project, tag
from jikan.core.entry import (
    EntryAlreadyRunningError,
    EntryNotFoundError,
    EntryNotRunningError,
    delete_entry,
    edit_entry,
    get_entry,
    get_running_entry,
    list_time_entry,
    running_time,
    start_time_entry,
    stop_time_entry,
)
from jikan.lib.datetime import format_datetime, format_timedelta
from jikan.lib.print import error, success, warn
from jikan.models import create_db_and_tables

console = Console()

app = Typer()


@app.command()
def init():
    create_db_and_tables()


app.add_typer(project.app, name="project")
app.add_typer(tag.app, name="tag")


@app.command()
def start(
    id: Annotated[int, typer.Option(help="ID of associated project", default=...)],
    title: Annotated[str, typer.Option("--title", "-t", help="Title of time entry")] = "",
    description: Annotated[
        str, typer.Option("--description", "-d", help="Description of time entry")
    ] = "",
):
    try:
        new_entry = start_time_entry(id, title, description)
        success(f"Time entry started at {new_entry.start_at}")
    except EntryAlreadyRunningError as e:
        error("Time entry is already running")
        raise typer.Exit(code=1) from e
    except Exception as e:
        error(f"Failed to start. {e}")
        raise typer.Exit(code=1) from e


@app.command()
def stop():
    try:
        entry = stop_time_entry()
        success(f"Time entry stopped at {entry.end_at}")
    except EntryNotRunningError as e:
        error("No time entry running")
        raise typer.Exit(code=1) from e
    except Exception as e:
        error(f"Failed to stop. {e}")
        raise typer.Exit(code=1) from e


@app.command()
def switch():
    warn("Not implemented.")


@app.command()
def status():
    running_entry = get_running_entry()

    if len(running_entry) == 0:
        print("No time entry running.")
        raise typer.Exit()
    elif len(running_entry) > 1:
        error("Multiple time entries running")
        raise typer.Exit(code=1)

    print(f"ID: {running_entry[0].id}")
    print(f"Title: {running_entry[0].title}")
    print(f"Description: {running_entry[0].description}")
    print(f"Time entry running: {format_timedelta(running_time(running_entry[0]))}")


@app.command()
def list():
    time_entries = list_time_entry()
    table = Table("ID", "Title", "Description", "Start at", "End at", "Created at", "Updated at")
    for entry in time_entries:
        table.add_row(
            str(entry.id),
            entry.title,
            entry.description,
            format_datetime(entry.start_at),
            format_datetime(entry.end_at) if entry.end_at is not None else "None",
            format_datetime(entry.created_at),
            format_datetime(entry.updated_at),
        )
    console.print(table)


@app.command()
def edit(
    id: Annotated[int, typer.Argument(help="ID of time entry to be edited")],
    title: Annotated[str | None, typer.Option("--title", "-t", help="Title of time entry")] = None,
    description: Annotated[
        str | None, typer.Option("--description", "-d", help="Description of time entry")
    ] = None,
):
    if title is None and description is None:
        error("Either title or description must be specified")
        raise typer.Exit(code=1) from None

    try:
        entry = get_entry(id)
        edit_entry(entry, title, description)
        success("Entry edited")
    except EntryNotFoundError as e:
        error("Entry not found")
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
def report():
    warn("Not implemented.")


@app.command()
def export():
    warn("Not implemented.")
