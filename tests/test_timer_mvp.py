"""TMR-01/02/03 acceptance tests, independent of main.py registration."""

import errno
import io
import os
import re
import select
import signal
import sqlite3
import struct
import sys
import time
from datetime import timedelta
from pathlib import Path

import pytest
import typer
from rich.console import Console
from sqlmodel import SQLModel, create_engine
from sqlmodel import select as sql_select
from typer.testing import CliRunner

from jikan.commands import timer as timer_module
from jikan.db import session_context
from jikan.lib.datetime import utc_now
from jikan.models import Entry


def _app() -> typer.Typer:
    app = typer.Typer()

    @app.callback()
    def root():
        pass

    app.command("timer")(timer_module.timer)
    return app


def _snapshot() -> list[dict]:
    with session_context() as session:
        return [entry.model_dump() for entry in session.exec(sql_select(Entry)).all()]


@pytest.mark.parametrize("title", [None, "", "  ", "PR #43 のレビュー", "[red]literal[/red]"])
@pytest.mark.parametrize("width,height", [(80, 24), (40, 12)])
def test_frame_has_title_clock_five_large_rows_and_close_hint(title, width, height):
    frame = timer_module._render_frame(
        title, timedelta(hours=1, minutes=18, seconds=6), width, height
    )
    lines = frame.plain.splitlines()
    assert "CURRENT TASK" in frame.plain
    assert (
        title.strip() in frame.plain if title and title.strip() else "Untitled task" in frame.plain
    )
    assert "01:18:06" in frame.plain
    assert "Ctrl+C" in frame.plain
    assert len([line for line in lines if "█" in line]) == 5
    assert len(lines) <= height
    assert all(line.cell_len <= width for line in frame.split("\n"))
    # The clock is centered horizontally and stays near the screen's vertical center.
    clock_line = next(line for line in lines if "01:18:06" in line)
    assert abs(clock_line.index("01:18:06") - (width - 8) // 2) <= 1
    block_start = next(index for index, line in enumerate(lines) if "█" in line)
    assert abs((block_start + 2) - height // 2) <= 2


@pytest.mark.parametrize("width,height", [(40, 12), (20, 6), (10, 3)])
def test_long_multiline_title_cannot_hide_elapsed(width, height):
    frame = timer_module._render_frame(
        "長いタイトル\n\x1b[31m" * 40, timedelta(seconds=7), width, height
    )
    assert "00:00:07" in frame.plain
    assert "\x1b" not in frame.plain
    assert len(frame.plain.splitlines()) <= height
    assert all(line.cell_len <= width for line in frame.split("\n"))


@pytest.mark.parametrize(
    "seconds,expected",
    [
        (0, "00:00:00"),
        (3661, "01:01:01"),
        (90061, "25:01:01"),
        (360000, "100:00:00"),
        (-1, "00:00:00"),
    ],
)
def test_elapsed_uses_total_hours(seconds, expected):
    assert timer_module._format_elapsed(timedelta(seconds=seconds)) == expected


def test_empty_state_exits_successfully_without_live_or_writes(use_test_engine, monkeypatch):
    monkeypatch.setattr(timer_module, "Live", lambda *a, **kw: pytest.fail("live started"))
    before = _snapshot()
    result = CliRunner().invoke(_app(), ["timer"])
    assert result.exit_code == 0
    assert "No time entry running" in result.output
    assert 'jikan start --title "' in result.output
    assert _snapshot() == before


def test_multiple_running_exits_nonzero_without_live_or_writes(seed_entries, monkeypatch):
    monkeypatch.setattr(timer_module, "Live", lambda *a, **kw: pytest.fail("live started"))
    before = _snapshot()
    result = CliRunner().invoke(_app(), ["timer"])
    assert result.exit_code != 0
    assert "Data error" in result.output
    assert "Multiple time entries running" in result.output
    assert "jikan list" in result.output
    assert _snapshot() == before


def test_live_refreshes_each_second_and_ctrl_c_preserves_entry(seed_active_entry, monkeypatch):
    monkeypatch.setenv("TERM", "xterm-256color")
    output = io.StringIO()
    monkeypatch.setattr(
        timer_module,
        "Console",
        lambda: Console(file=output, force_terminal=True, width=80, height=24),
    )
    now = utc_now()
    with session_context() as session:
        entry = session.get(Entry, 1)
        entry.start_at = now - timedelta(seconds=59)
        session.add(entry)
        session.commit()
    monkeypatch.setattr("jikan.core.entry.utc_now", lambda: now)
    calls = []

    def tick(seconds):
        nonlocal now
        calls.append(seconds)
        assert _snapshot() == before
        now += timedelta(seconds=1)
        if len(calls) == 3:
            raise KeyboardInterrupt

    monkeypatch.setattr(timer_module, "sleep", tick)
    before = _snapshot()
    timer_module.timer()
    assert calls == [1, 1, 1]
    assert all(clock in output.getvalue() for clock in ["00:00:59", "00:01:00", "00:01:01"]), repr(
        output.getvalue()
    )
    assert "\x1b[?25h" in output.getvalue()  # Cursor restored after Ctrl+C.
    assert _snapshot() == before


@pytest.mark.skipif(sys.platform == "win32", reason="requires POSIX PTYs")
@pytest.mark.parametrize("width,height", [(80, 24), (40, 12)])
def test_pty_redraw_ctrl_c_and_database_unchanged(tmp_path, width, height):
    import fcntl
    import pty
    import termios

    home = tmp_path / "home"
    database = home / ".jikan" / "database.db"
    database.parent.mkdir(parents=True)
    engine = create_engine(f"sqlite:///{database}")
    SQLModel.metadata.create_all(engine)
    from sqlmodel import Session

    with Session(engine) as session:
        session.add(
            Entry(title="PR #43 のレビュー " * 12, start_at=utc_now() - timedelta(seconds=59))
        )
        session.commit()
    engine.dispose()

    def dump():
        with sqlite3.connect(database) as connection:
            return list(connection.iterdump())

    before = dump()
    environment = os.environ.copy()
    environment.update(
        HOME=str(home),
        TERM="xterm-256color",
        COLUMNS=str(width),
        LINES=str(height),
        PYTHONPATH=str(Path(__file__).resolve().parents[1] / "src"),
    )
    bootstrap = (
        "import typer; from jikan.commands.timer import timer; "
        "app=typer.Typer(); app.command('timer')(timer); app()"
    )
    pid, master = pty.fork()
    if pid == 0:
        os.execve(sys.executable, [sys.executable, "-c", bootstrap], environment)
    reaped = False
    captured = bytearray()

    def read_until(predicate, timeout=10):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if select.select([master], [], [], 0.1)[0]:
                try:
                    data = os.read(master, 65536)
                except OSError as exc:
                    if exc.errno != errno.EIO:
                        raise
                    break
                if not data:
                    break
                captured.extend(data)
                if predicate(captured.decode("utf-8", errors="replace")):
                    return
        pytest.fail(f"PTY output did not meet condition: {captured.decode(errors='replace')!r}")

    try:
        fcntl.ioctl(master, termios.TIOCSWINSZ, struct.pack("HHHH", height, width, 0, 0))
        read_until(lambda text: bool(re.search(r"\d{2}:\d{2}:\d{2}", text)))
        first = re.search(rb"\d{2}:\d{2}:\d{2}", captured).group().decode()
        first_frame = captured.decode("utf-8")
        assert "CURRENT TASK" in first_frame and "PR #43" in first_frame
        assert "Ctrl+C" in first_frame
        assert len([line for line in first_frame.splitlines() if "█" in line]) >= 5
        assert dump() == before
        read_until(
            lambda text: any(clock != first for clock in re.findall(r"\d{2}:\d{2}:\d{2}", text))
        )
        clocks = re.findall(rb"\d{2}:\d{2}:\d{2}", captured)

        def to_seconds(clock):
            return sum(
                int(part) * scale
                for part, scale in zip(clock.split(b":"), (3600, 60, 1), strict=True)
            )

        assert to_seconds(clocks[-1]) >= to_seconds(clocks[0]) + 1
        os.write(master, b"\x03")
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            child, status = os.waitpid(pid, os.WNOHANG)
            if child:
                reaped = True
                assert os.waitstatus_to_exitcode(status) == 0
                break
            if select.select([master], [], [], 0.1)[0]:
                try:
                    captured.extend(os.read(master, 65536))
                except OSError as exc:
                    if exc.errno != errno.EIO:
                        raise
        assert reaped, "timer did not exit after terminal Ctrl+C"
        assert dump() == before
        # Use the existing status command against the same DB after closing the view.
        import subprocess

        status = subprocess.run(
            [sys.executable, "-c", "from jikan.main import app; app()", "status"],
            env=environment,
            capture_output=True,
            text=True,
            check=False,
            timeout=10,
        )
        assert status.returncode == 0, status.stderr
        assert "PR #43" in status.stdout
        assert "No time entry running" not in status.stdout
        assert dump() == before
    finally:
        if not reaped:
            os.kill(pid, signal.SIGKILL)
            os.waitpid(pid, 0)
        os.close(master)
