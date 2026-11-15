"""Read-only live timer. Register with ``app.command('timer')(timer)``."""

from datetime import timedelta
from time import sleep

import typer
from rich.console import Console
from rich.live import Live
from rich.text import Text
from sqlalchemy.exc import SQLAlchemyError

from jikan.core.entry import get_running_entry, running_time

# Three cells per digit keep even a five-line clock legible in a 40-column pane.
_DIGITS = {
    "0": ("███", "█ █", "█ █", "█ █", "███"),
    "1": (" █ ", "██ ", " █ ", " █ ", "███"),
    "2": ("███", "  █", "███", "█  ", "███"),
    "3": ("███", "  █", "███", "  █", "███"),
    "4": ("█ █", "█ █", "███", "  █", "  █"),
    "5": ("███", "█  ", "███", "  █", "███"),
    "6": ("███", "█  ", "███", "█ █", "███"),
    "7": ("███", "  █", "  █", "  █", "  █"),
    "8": ("███", "█ █", "███", "█ █", "███"),
    "9": ("███", "█ █", "███", "  █", "███"),
    ":": (" ", "█", " ", "█", " "),
}


def _format_elapsed(elapsed: timedelta) -> str:
    # Keep total hours (rather than wrapping at midnight).
    seconds = max(0, int(elapsed.total_seconds()))
    hours, seconds = divmod(seconds, 3600)
    minutes, seconds = divmod(seconds, 60)
    return f"{hours:02}:{minutes:02}:{seconds:02}"


def _render_frame(title: str | None, elapsed: timedelta, width: int, height: int) -> Text:
    """Fit a frame in terminal cells, reserving room for the elapsed time first."""
    width, height = max(1, width), max(1, height)
    clock = _format_elapsed(elapsed)
    # Titles are literal text; newlines/control characters cannot displace the clock.
    title = " ".join((title or "").split()) or "Untitled task"
    title = "".join(character for character in title if character.isprintable())
    title = title or "Untitled task"
    large = [" ".join(_DIGITS[digit][row] for digit in clock) for row in range(5)]
    if len(large[0]) <= width and height >= 10:
        lines = ["CURRENT TASK", title, "", *large, clock, "Press Ctrl+C to close this view"]
    else:
        # For panes smaller than the supported 40x12, retain a readable clock.
        lines = ["CURRENT TASK", title, clock, "Ctrl+C to close"]
        if height < len(lines):
            lines = [title, clock, "Ctrl+C to close"] if height >= 3 else [title, clock]
            if height == 1:
                lines = [clock]

    frame = Text(no_wrap=True, overflow="crop")
    top = max(0, (height - len(lines)) // 2)
    frame.append("\n" * top)
    for index, line in enumerate(lines):
        text = Text(line)
        text.truncate(width, overflow="ellipsis")
        text.align("center", width)
        frame.append_text(text)
        if index < len(lines) - 1:
            frame.append("\n")
    return frame


def timer() -> None:
    """Show the current task and elapsed time; Ctrl+C closes only the view."""
    console = Console()
    try:
        entries = get_running_entry()
    except SQLAlchemyError as exc:
        typer.echo(
            "Cannot read time entries. Check the database; run `jikan init` for setup.", err=True
        )
        raise typer.Exit(code=1) from exc

    if not entries:
        typer.echo('No time entry running. Start one with: jikan start --title "My task"')
        return
    if len(entries) > 1:
        typer.echo(
            "Data error: Multiple time entries running. "
            "Check `jikan list` and repair the records before opening the timer.",
            err=True,
        )
        raise typer.Exit(code=1)

    entry = entries[0]

    def frame() -> Text:
        width, height = console.size
        return _render_frame(entry.title, running_time(entry), width, height)

    try:
        with Live(frame(), console=console, screen=True, auto_refresh=False) as live:
            while True:
                sleep(1)
                live.update(frame(), refresh=True)
    except KeyboardInterrupt:
        # Live restores the cursor/screen; the entry is never written or stopped.
        return
