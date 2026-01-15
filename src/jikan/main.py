import typer
from rich import print
from rich.console import Console
from rich.table import Table
from typer import Typer, colors, echo, style

from jikan.commands import project, tag
from jikan.models import create_db_and_tables

console = Console()

app = Typer()


@app.command()
def init():
    create_db_and_tables()


app.add_typer(project.app, name="project")
app.add_typer(tag.app, name="tag")


@app.command()
def start():
    print("Not implemented.")


@app.command()
def stop():
    print("Not implemented.")


@app.command()
def switch():
    print("Not implemented.")


@app.command()
def status():
    print("Jikan version 0.1.0 :boom:")


@app.command()
def list():
    print("Not implemented.")


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
