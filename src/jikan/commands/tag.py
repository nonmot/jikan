from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from jikan.core.tag import TagNotFoundError, add_tag, delete_tag, edit_tag, get_tag, list_tag
from jikan.lib.print import error, success

console = Console()

app = typer.Typer()


@app.command()
def list():
    """List tags"""
    table = Table("ID", "Name")
    tags = list_tag()
    for tag in tags:
        table.add_row(str(tag.id), tag.name)
    console.print(table)


@app.command()
def add(name: Annotated[str, typer.Option(help="Name of tag", default=...)]):
    """Add new tag"""
    new_tag = add_tag(name)
    success(f"Tag created. name: {new_tag.name}")


@app.command()
def edit(
    id: Annotated[int, typer.Option(help="ID of tag to be edited", default=...)],
    name: Annotated[str, typer.Option(help="Name of tag", default=...)],
):
    try:
        tag = get_tag(id)
        updated_tag = edit_tag(tag, name)
        success(f"Tag edited. name: {updated_tag.name}")
    except TagNotFoundError as e:
        error("Tag not found")
        raise typer.Exit(code=1) from e
    except Exception as e:
        error(f"Failed to edit tag: {e}")
        raise typer.Exit(code=1) from e


@app.command()
def delete(id: Annotated[int, typer.Option(help="ID of tag to be deleted", default=...)]):
    try:
        tag = get_tag(id)
        print(tag.model_dump())
        _ = typer.confirm("Are you sure you want to delete it?", abort=True)
        delete_tag(tag)
        success("Tag deleted.")
    except TagNotFoundError as e:
        error("Tag not found")
        raise typer.Exit(code=1) from e
    except Exception as e:
        error(f"Failed to delete tag: {e}")
        raise typer.Exit(code=1) from e
