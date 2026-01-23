import typer
from typer import echo


def error(message: str) -> None:
    err_msg = typer.style("Error", fg=typer.colors.RED)
    echo(err_msg + ": " + message)


def warn(message: str) -> None:
    warn_msg = typer.style("Warning", fg=typer.colors.YELLOW)
    echo(warn_msg + ": " + message)


def success(message: str) -> None:
    success_msg = typer.style("Success", fg=typer.colors.GREEN)
    echo(success_msg + ": " + message)
