"""TMR-01/02/03: public CLI in actual 80x24 and 40x12 POSIX terminals."""

import errno
import os
import re
import select
import signal
import sqlite3
import struct
import sys
import time

import pytest


@pytest.mark.skipif(sys.platform == "win32", reason="requires POSIX PTYs")
@pytest.mark.parametrize("width,height", [(80, 24), (40, 12)])
def test_tmr_01_02_03_public_cli_pty(classified, database_path, width, height):
    import fcntl
    import pty
    import termios

    cli = classified
    # A live display must advance with wall time. Only these children omit the fixed clock.
    result = cli("start", "--title", "PR #43 のレビュー " * 12, now=None)
    assert result.returncode == 0, result.stdout + result.stderr

    def dump():
        with sqlite3.connect(database_path) as connection:
            return list(connection.iterdump())

    before = dump()
    initial_status = cli("status", now=None)
    assert initial_status.returncode == 0
    environment = cli.environment(
        now=None, extra={"TERM": "xterm-256color", "COLUMNS": str(width), "LINES": str(height)}
    )
    pid, master = pty.fork()
    if pid == 0:
        os.execve(cli.command[0], [*cli.command, "timer"], environment)
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
        assert dump() == before
        second_frame = captured.decode("utf-8", errors="replace").rsplit("CURRENT TASK", 1)[-1]
        assert "PR #43" in second_frame and "Ctrl+C" in second_frame
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
        status = cli("status", now=None)
        assert status.returncode == 0, status.stderr
        assert "PR #43" in status.stdout
        assert "No time entry running" not in status.stdout
        elapsed = r"Time entry running: (\d+)h (\d+)m (\d+)s"

        def elapsed_seconds(output):
            match = re.search(elapsed, output)
            assert match, output
            return sum(
                int(value) * scale
                for value, scale in zip(match.groups(), (3600, 60, 1), strict=True)
            )

        assert elapsed_seconds(status.stdout) > elapsed_seconds(initial_status.stdout)
        assert dump() == before
    finally:
        if not reaped:
            os.kill(pid, signal.SIGKILL)
            os.waitpid(pid, 0)
        os.close(master)


def test_tmr_03_empty_state(classified, database_path):
    from .conftest import ok, snapshot

    before = snapshot(database_path)
    output = ok(classified("timer"))
    assert "No time entry running" in output
    assert "start --title" in output
    assert "\x1b[?1049h" not in output
    assert snapshot(database_path) == before
