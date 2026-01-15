from typing import Annotated

import typer
from rich import print
from rich.console import Console
from rich.table import Table

from jikan.core.project import (
    ProjectNotFoundError,
    add_project,
    delete_project,
    edit_project,
    get_project,
    list_project,
    set_project_archived,
)
from jikan.lib.print import error, success

console = Console()

app = typer.Typer()


@app.command()
def list():
    """List projects"""
    table = Table("ID", "Name", "Description")
    projects = list_project()
    for project in projects:
        table.add_row(str(project.id), project.name, project.description)
    console.print(table)


@app.command()
def add(
    name: Annotated[str, typer.Option(help="Name of project", default=...)],
    description: Annotated[
        str, typer.Option("--description", "-d", help="Description of project")
    ] = "",
):
    """Add new project"""
    new_project = add_project(name, description)
    success(f"Project created. name: {new_project.name}, description: {new_project.description}")


@app.command()
def delete(id: Annotated[int, typer.Option(help="ID of project to be deleted", default=...)]):
    try:
        project = get_project(id)
        print(project.model_dump())
        _ = typer.confirm("Are you sure you want to delete it?", abort=True)
        delete_project(project)
        success("Project deleted.")
    except ProjectNotFoundError as e:
        error("Project not found")
        raise typer.Exit(code=1) from e
    except Exception as e:
        error(f"Failed to delete project: {e}")
        raise typer.Exit(code=1) from e


@app.command()
def edit(
    id: Annotated[int, typer.Option(help="ID of project to be edited", default=...)],
    name: Annotated[str | None, typer.Option(help="Name of project")] = None,
    description: Annotated[
        str | None, typer.Option("--description", "-d", help="Description of project")
    ] = None,
):
    if not name and not description:
        error("You must specify either name or description")
        raise typer.Exit(code=1)

    try:
        project = get_project(id)
        updated_project = edit_project(project, name, description)
        success(f"project edited. name: {updated_project.name}, description: {project.description}")
    except ProjectNotFoundError as e:
        error("Project not found")
        raise typer.Exit(code=1) from e
    except Exception as e:
        error(f"Failed to edit project: {e}")
        raise typer.Exit(code=1) from e


@app.command()
def archive(id: Annotated[int, typer.Option(help="ID of project to be archived", default=...)]):
    try:
        project = get_project(id)
        set_project_archived(project, True)
        success(f"Project {project.id} is archived")
    except ProjectNotFoundError as e:
        error("Project not found")
        raise typer.Exit(code=1) from e
    except Exception as e:
        error(f"Failed to archive project: {e}")
        raise typer.Exit(code=1) from e


@app.command()
def unarchive(id: Annotated[int, typer.Option(help="ID of project to be unarchived", default=...)]):
    try:
        project = get_project(id)
        set_project_archived(project, False)
        success(f"Project {project.id} is unarchived")
    except ProjectNotFoundError as e:
        error("Project not found")
        raise typer.Exit(code=1) from e
    except Exception as e:
        raise typer.Exit(code=1) from e
