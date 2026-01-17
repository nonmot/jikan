from typing import Annotated
import typer
from rich import print
from rich.console import Console
from rich.table import Table
from typer import Typer, colors, echo, style

from jikan.commands import project, tag
from jikan.core.entry import get_running_entry, list_time_entry, running_time, start_time_entry, stop_time_entry
from jikan.lib.datetime import format_datetime, format_timedelta
from jikan.models import create_db_and_tables
from jikan.lib.print import error

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
    description: Annotated[str, typer.Option(help="Description of time entry")] = "",
):
    try:
        start_time_entry(id, description)
    except Exception as e:
        error(f"Failed to start. {e}")
        raise typer.Exit(code=1)


@app.command()
def stop():
    try:
        stop_time_entry()
    except Exception as e:
        error(f"Failed to stop. {e}")
        raise typer.Exit(code=1)


@app.command()
def switch():
    print("Not implemented.")


@app.command()
def status():
    running_entry = get_running_entry()

    if len(running_entry) == 0:
        print("No time entry running.")
        raise typer.Exit()
    elif len(running_entry) > 1:
        error("Multiple time entry running")
        raise typer.Exit(code=1)
    
    print(f"Time entry running: {format_timedelta(running_time(running_entry[0]))}s")


@app.command()
def list():
    time_entries = list_time_entry()
    table = Table("ID", "Description", "Start at", "End at", "Created at", "Updated at")
    for entry in time_entries:
        table.add_row(
            str(entry.id),
            entry.description,
            format_datetime(entry.start_at),
            format_datetime(entry.end_at) if entry.end_at is not None else "None",
            format_datetime(entry.created_at),
            format_datetime(entry.updated_at),
        )
    console.print(table)


@app.command()
def edit():
    print("Not implemented.")


@app.command()
def delete():
    print("Not implemented.")


@app.command()
def report():
    print("Not implemented.")


@app.command()
def export():
    print("Not implemented.")


@app.command()
def dev():
    """For development"""
    msg_warning = style("Warning", fg=colors.WHITE, bg=colors.RED)
    echo(msg_warning + ": This is a command for development.")

    table = Table("Name", "Item")
    table.add_row("Package", "Jikan")
    table.add_row("Version", "0.1.0")
    table.add_row("Auther", "nonmot")
    console.print(table)

    raise typer.Exit(code=1)
