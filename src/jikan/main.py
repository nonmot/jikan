import typer
from rich import print
from rich.console import Console
from rich.table import Table
from typer import Typer, colors, echo, style

console = Console()

app = Typer()


@app.command()
def project():
    print("Not implemented.")


@app.command()
def tag():
    print("Not implemented.")


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
