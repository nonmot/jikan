"""Recording acceptance coverage, including real subprocess clock/SQLite races."""

import os
import sqlite3
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path

import pytest
from sqlalchemy import event
from typer.testing import CliRunner

from jikan.core.entry import (
    edit_entry,
    get_entry,
    get_running_entry,
    start_time_entry,
    switch_time_entry,
)
from jikan.core.project import add_project
from jikan.core.tag import TagNotFoundError, add_tag
from jikan.db import session_context
from jikan.lib.datetime import ensure_utc_aware, utc_now
from jikan.main import app

START = "2026-10-21T09:00:00+09:00"
SWITCH = "2026-10-21T09:42:18+09:00"
STOP = "2026-10-21T11:00:00+09:00"
runner = CliRunner()


@pytest.fixture()
def recording(use_test_engine, monkeypatch):
    monkeypatch.setenv("JIKAN_TEST_NOW", START)
    add_project("client-web", "Web")
    add_project("jikan", "CLI")
    for name in ("development", "frontend", "review"):
        add_tag(name)


def invoke(*args):
    result = runner.invoke(app, args)
    assert result.exit_code == 0, result.output + repr(result.exception)
    return result.output


def test_classified_start_status_switch_stop(recording, monkeypatch):
    started = invoke(
        "start",
        "--title",
        "ログイン [bold]",
        "--project",
        "client-web",
        "--tag",
        "development",
        "--tag",
        "frontend",
        "--tag",
        "frontend",
    )
    for value in ("ID: 1", "ログイン [bold]", "client-web", "development, frontend", "09:00:00"):
        assert value in started
    original = get_entry(1)
    assert original.project.name == "client-web"
    assert [tag.name for tag in original.tags] == ["development", "frontend"]
    assert ensure_utc_aware(original.start_at) == datetime(2026, 10, 21, tzinfo=UTC)

    monkeypatch.setenv("JIKAN_TEST_NOW", SWITCH)
    status = invoke("status")
    for value in ("Running #1", "ログイン [bold]", "client-web", "frontend", "00h 42m 18s"):
        assert value in status
    duplicate = runner.invoke(app, ["start", "--title", "Other"])
    assert duplicate.exit_code == 1
    for value in ("ログイン [bold]", "09:00:00", "client-web", "jikan switch", "jikan stop"):
        assert value in duplicate.output
    assert len(get_running_entry()) == 1

    switched = invoke("switch", "--title", "Review", "--project", "jikan", "--tag", "review")
    assert "Stopped #1" in switched and "Started #2" in switched
    stopped, running = get_entry(1), get_running_entry()[0]
    assert stopped.end_at == running.start_at
    assert running.project.name == "jikan" and running.tags[0].name == "review"
    monkeypatch.setenv("JIKAN_TEST_NOW", STOP)
    stopped_output = invoke("stop")
    for value in ("Review", "11:00:00", "01h 17m 42s"):
        assert value in stopped_output
    stopped = get_entry(2)
    assert ensure_utc_aware(stopped.end_at) == utc_now()
    assert get_running_entry() == []
    assert "jikan start --title" in invoke("status")
    no_stop = runner.invoke(app, ["stop"])
    assert no_stop.exit_code == 1 and "jikan status" in no_stop.output
    assert get_entry(2).end_at == stopped.end_at


def test_unclassified_start_and_empty_switch(recording):
    output = invoke("switch", "--title", "Inbox")
    assert "No time entry running" in output
    assert "Unassigned" in output
    entry = get_running_entry()[0]
    assert entry.project is None and entry.tags == []
    invoke("stop")
    assert "Unassigned" in invoke("start", "--title", "Mail")
    entry = get_running_entry()[0]
    assert entry.project is None and entry.tags == []


@pytest.mark.parametrize("option,kind", [("--project", "project"), ("--tag", "tag")])
@pytest.mark.parametrize("command", ["start", "switch"])
def test_unknown_names_fail_without_creating(recording, option, kind, command):
    result = runner.invoke(app, [command, "--title", "Invalid", option, "missing"])
    assert result.exit_code == 1
    assert "missing" in result.output
    assert f"jikan {kind} list" in result.output
    assert f"jikan {kind} add" in result.output
    assert get_running_entry() == []


@pytest.mark.parametrize(
    "args",
    [
        ["--project", "missing"],
        ["--tag", "missing"],
        ["--project-id", "999"],
        ["--project", "client-web", "--project-id", "1"],
    ],
)
def test_invalid_switch_preserves_old_entry(recording, args):
    entry = start_time_entry(
        None, "Original", "", project_name="client-web", tag_names=["frontend"]
    )
    result = runner.invoke(app, ["switch", "--title", "Invalid", *args])
    assert result.exit_code == 1
    after = get_running_entry()
    assert len(after) == 1 and after[0].id == entry.id
    assert after[0].start_at == entry.start_at and after[0].end_at is None
    assert after[0].project.name == "client-web" and after[0].tags[0].name == "frontend"
    with session_context() as session:
        assert session.connection().exec_driver_sql("SELECT COUNT(*) FROM entry").scalar() == 1


@pytest.mark.parametrize("option", ["--project-id", "--id"])
def test_project_id_compatibility(recording, option):
    assert "client-web" in invoke("start", "--title", "Task", option, "1")
    assert get_running_entry()[0].project_id == 1


def test_invalid_project_id_and_conflicting_options(recording):
    for args in (["--project-id", "999"], ["--project", "client-web", "--id", "1"]):
        result = runner.invoke(app, ["start", "--title", "Invalid", *args])
        assert result.exit_code == 1
        assert get_running_entry() == []


def test_switch_rolls_back_when_insert_fails(recording):
    original = start_time_entry(None, "Original", "")
    with session_context() as session:
        engine = session.get_bind()

    def fail_insert(connection, cursor, statement, parameters, context, executemany):
        if statement.startswith("INSERT INTO entry "):
            raise RuntimeError("simulated persistence failure")

    event.listen(engine, "before_cursor_execute", fail_insert)
    try:
        with pytest.raises(RuntimeError, match="persistence failure"):
            switch_time_entry(None, "New", "")
    finally:
        event.remove(engine, "before_cursor_execute", fail_insert)
    assert get_entry(original.id).end_at is None
    assert len(get_running_entry()) == 1


def test_future_start_refuses_stop_and_switch(recording, monkeypatch):
    original = start_time_entry(None, "Original", "")
    monkeypatch.setenv("JIKAN_TEST_NOW", "2026-10-20T00:00:00Z")
    for command in ("stop", "switch"):
        result = runner.invoke(app, [command])
        assert result.exit_code == 1 and "future" in result.output
        assert get_running_entry()[0].id == original.id
        assert get_entry(original.id).end_at is None


def test_edit_api_keeps_relationships_and_rolls_back(recording):
    original = start_time_entry(1, "Original", "", tag_names=["frontend"])
    with pytest.raises(TagNotFoundError, match="Tag not found"):
        edit_entry(original, title="Bad", project_id=2, add_tags_id=[999])
    after = get_entry(original.id)
    assert after.title == "Original" and after.project.name == "client-web"
    assert [tag.name for tag in after.tags] == ["frontend"]
    edited = edit_entry(after, title="Updated", project_id=2, add_tags_id=[3], remove_tags_id=[2])
    assert edited.title == "Updated" and edited.project.name == "jikan"
    assert [tag.name for tag in edited.tags] == ["review"]


@pytest.mark.parametrize("value", ["invalid", "2026-10-21T09:00:00"])
def test_fixed_clock_requires_timezone(monkeypatch, value):
    monkeypatch.setenv("JIKAN_TEST_NOW", value)
    with pytest.raises(ValueError, match="JIKAN_TEST_NOW"):
        utc_now()


@pytest.fixture()
def subprocess_cli(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    environment = os.environ.copy()
    environment.update(
        {"HOME": str(home), "JIKAN_TEST_NOW": START, "NO_COLOR": "1", "COLUMNS": "200"}
    )
    source = str(Path(__file__).resolve().parents[1] / "src")
    environment["PYTHONPATH"] = source + os.pathsep + environment.get("PYTHONPATH", "")

    def run(*args, now=START):
        return subprocess.run(
            [sys.executable, "-c", "from jikan.main import app; app()", *args],
            env={**environment, "JIKAN_TEST_NOW": now},
            text=True,
            capture_output=True,
            timeout=45,
            check=False,
        )

    return run, home / ".jikan" / "database.db"


def test_subprocess_setup_clock_and_competing_starts(subprocess_cli):
    cli, path = subprocess_cli
    initialized = cli("init")
    assert initialized.returncode == 0 and str(path) in initialized.stdout
    assert "project add" in initialized.stdout and "tag add" in initialized.stdout
    assert cli("project", "add", "--name", "client-web").returncode == 0
    assert cli("tag", "add", "--name", "frontend").returncode == 0
    with sqlite3.connect(path) as connection:
        assert connection.execute("SELECT COUNT(*) FROM entry").fetchone()[0] == 0
    with ThreadPoolExecutor(max_workers=4) as executor:
        results = list(executor.map(lambda n: cli("start", "--title", f"Task {n}"), range(4)))
    assert sorted(result.returncode for result in results) == [0, 1, 1, 1]
    for result in results:
        if result.returncode:
            assert "already running" in result.stdout and "jikan switch" in result.stdout
    with sqlite3.connect(path) as connection:
        row = connection.execute("SELECT start_at, end_at FROM entry").fetchall()
        assert row == [("2026-10-21 00:00:00.000000", None)]
    assert "00h 42m 18s" in cli("status", now=SWITCH).stdout
    assert cli("stop", now=STOP).returncode == 0
    assert cli("init").returncode == 0
    with sqlite3.connect(path) as connection:
        assert connection.execute("SELECT COUNT(*) FROM entry").fetchone()[0] == 1
        assert (
            connection.execute("SELECT end_at FROM entry").fetchone()[0]
            == "2026-10-21 02:00:00.000000"
        )


@pytest.mark.parametrize("command", ["start", "switch", "stop", "status"])
def test_legacy_multiple_running_entries_are_reported_without_mutation(seed_entries, command):
    result = runner.invoke(app, [command])
    assert result.exit_code == 1
    assert "Multiple time entries running" in result.output
    assert len(get_running_entry()) == 2
    assert get_entry(1).end_at is None and get_entry(2).end_at is None


def test_concurrent_subprocess_switches_keep_one_running(subprocess_cli):
    cli, path = subprocess_cli
    assert cli("init").returncode == 0
    assert cli("start", "--title", "Original").returncode == 0
    with ThreadPoolExecutor(max_workers=4) as executor:
        results = list(
            executor.map(lambda n: cli("switch", "--title", f"Task {n}", now=SWITCH), range(4))
        )
    assert all(result.returncode == 0 for result in results)
    with sqlite3.connect(path) as connection:
        rows = connection.execute("SELECT id, start_at, end_at FROM entry ORDER BY id").fetchall()
    assert len(rows) == 5
    assert sum(row[2] is None for row in rows) == 1
    assert rows[-1][2] is None
    for before, after in zip(rows, rows[1:], strict=False):
        assert before[2] == after[1] == "2026-10-21 00:42:18.000000"
