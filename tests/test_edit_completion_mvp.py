"""T4 edit atomicity, timezone input, integration and real shell completion."""

import os
import sqlite3
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

import click
import pytest
from sqlalchemy import event
from typer.main import get_command
from typer.testing import CliRunner

from jikan.completion import complete_projects, complete_tags
from jikan.core.entry import edit_entry, get_entry, start_time_entry, stop_time_entry
from jikan.core.project import add_project
from jikan.core.tag import add_tag
from jikan.db import session_context
from jikan.lib import datetime as dt
from jikan.main import app

runner = CliRunner()


@pytest.fixture()
def recorded(use_test_engine, monkeypatch):
    monkeypatch.setenv("JIKAN_TEST_NOW", "2026-10-21T09:00:00+09:00")
    monkeypatch.setattr(dt.config, "timezone", "Asia/Tokyo")
    add_project("client-web", "")
    add_project("jikan", "")
    for name in ("development", "frontend", "review"):
        add_tag(name)
    start_time_entry(1, "Original [bold]", "Before", tag_names=["development", "frontend"])
    monkeypatch.setenv("JIKAN_TEST_NOW", "2026-10-21T11:00:00+09:00")
    return stop_time_entry()


def snapshot():
    with session_context() as session:
        connection = session.connection()
        return (
            connection.exec_driver_sql("SELECT * FROM entry ORDER BY id").fetchall(),
            connection.exec_driver_sql("SELECT * FROM entrytaglink ORDER BY tag_id").fetchall(),
        )


def test_edit_all_fields_names_and_local_iso_input(recorded):
    result = runner.invoke(
        app,
        [
            "edit",
            "1",
            "--title",
            "Changed [bold]",
            "--description",
            "After",
            "--start",
            "2026-10-21 09:30",
            "--end",
            "2026-10-21T03:00:00+00:00",
            "--project",
            "jikan",
            "--tag",
            "review",
            "--tag",
            "review",
            "--remove-tag",
            "frontend",
        ],
    )
    assert result.exit_code == 0, result.output
    for value in (
        "Updated #1",
        "Changed [bold]",
        "After",
        "09:30:00",
        "12:00:00",
        "jikan",
        "development, review",
        "02h 30m 00s",
    ):
        assert value in result.output
    after = get_entry(1)
    assert dt.ensure_utc_aware(after.start_at) == datetime(2026, 10, 21, 0, 30, tzinfo=UTC)
    assert dt.ensure_utc_aware(after.end_at) == datetime(2026, 10, 21, 3, tzinfo=UTC)
    assert after.project.name == "jikan"
    assert [tag.name for tag in after.tags] == ["development", "review"]
    viewed = runner.invoke(app, ["view", "1"])
    assert viewed.exit_code == 0
    for value in ("Changed", "After", "09:30:00", "12:00:00", "jikan", "review"):
        assert value in viewed.output
    assert "Changed [bold]" in runner.invoke(app, ["list", "--all"]).output


@pytest.mark.parametrize(
    "extra",
    [
        ["--tag", "missing"],
        ["--add-tag", "999"],
        ["--remove-tag", "missing"],
        ["--project", "missing"],
        ["--project-id", "999"],
        ["--project", "jikan", "--project-id", "1"],
        ["--end", "2026-10-21 08:00"],
        ["--start", "bad"],
    ],
)
def test_invalid_edit_preserves_every_field_and_link(recorded, extra):
    before = snapshot()
    result = runner.invoke(
        app, ["edit", "1", "--title", "Bad", "--description", "Bad", "--tag", "review", *extra]
    )
    assert result.exit_code == 1, result.output
    assert snapshot() == before
    if "missing" in extra:
        assert "list" in result.output and "add --name" in result.output


def test_failure_during_link_insert_rolls_back_fields(recorded):
    before = snapshot()
    with session_context() as session:
        engine = session.get_bind()

    def fail(connection, cursor, statement, parameters, context, executemany):
        if statement.startswith("INSERT INTO entrytaglink"):
            raise RuntimeError("simulated link failure")

    event.listen(engine, "before_cursor_execute", fail)
    try:
        with pytest.raises(RuntimeError, match="link failure"):
            edit_entry(recorded, title="Bad", project_name="jikan", tag_names=["review"])
    finally:
        event.remove(engine, "before_cursor_execute", fail)
    assert snapshot() == before


def test_numeric_names_win_and_explicit_ids_remain_available(recorded):
    add_project("1", "")
    add_tag("2")
    for args in (["--project", "1", "--tag", "2"], ["--remove-tag", "2"]):
        assert runner.invoke(app, ["edit", "1", *args]).exit_code == 0
    after = get_entry(1)
    assert after.project.name == "1"
    assert {tag.name for tag in after.tags} == {"development", "frontend"}
    assert (
        runner.invoke(
            app, ["edit", "1", "--project-id", "1", "--add-tag", "3", "--remove-tag-id", "2"]
        ).exit_code
        == 0
    )
    after = get_entry(1)
    assert after.project.name == "client-web"
    assert {tag.name for tag in after.tags} == {"development", "review"}


def test_legacy_numeric_project_and_remove_tag_fallback(recorded):
    result = runner.invoke(app, ["edit", "1", "--project", "2", "--remove-tag", "2"])
    assert result.exit_code == 0, result.output
    assert get_entry(1).project.name == "jikan"
    assert [tag.name for tag in get_entry(1).tags] == ["development"]


@pytest.mark.parametrize(
    "value",
    [
        "2026-10-21 09:30",
        "2026/10/21 09:30:00",
        "2026-10-21T09:30:00+09:00",
        "2026-10-21T00:30:00Z",
    ],
)
def test_datetime_formats_use_configured_timezone(monkeypatch, value):
    monkeypatch.setattr(dt.config, "timezone", "Asia/Tokyo")
    assert dt.parse_dt(value) == datetime(2026, 10, 21, 0, 30, tzinfo=UTC)


def test_datetime_uses_non_default_timezone(monkeypatch):
    monkeypatch.setattr(dt.config, "timezone", "America/New_York")
    assert dt.parse_dt("2026-10-21 09:30") == datetime(2026, 10, 21, 13, 30, tzinfo=UTC)
    with pytest.raises(click.BadParameter):
        dt.parse_dt("2026-03-08 02:30")


@pytest.mark.parametrize("command", ["start", "switch", "edit", "list", "report", "export"])
@pytest.mark.parametrize(
    "option,prefix,expected", [("--project", "cli", "client-web"), ("--tag", "f", "frontend")]
)
def test_all_classification_options_complete_from_db(recorded, command, option, prefix, expected):
    group = get_command(app)
    ctx = click.Context(group)
    cmd = group.get_command(ctx, command)
    param = next(param for param in cmd.params if option in param.opts)
    assert [item.value for item in param.shell_complete(click.Context(cmd), prefix)] == [expected]


def test_completion_refreshes_after_add_rename_delete(recorded):
    assert complete_projects("cli") == ["client-web"]
    assert complete_tags("r") == ["review"]
    with session_context() as session:
        session.connection().exec_driver_sql("UPDATE tag SET name='renamed' WHERE name='review'")
        session.commit()
    assert complete_tags("re") == ["renamed"]
    with session_context() as session:
        session.connection().exec_driver_sql("DELETE FROM tag WHERE name='renamed'")
        session.commit()
    assert complete_tags("re") == []
    add_tag("recent")
    assert complete_tags("re") == ["recent"]


@pytest.fixture()
def cli(tmp_path):
    environment = {
        **os.environ,
        "HOME": str(tmp_path),
        "NO_COLOR": "1",
        "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src"),
    }

    def run(*args, env=None):
        return subprocess.run(
            [sys.executable, "-c", 'from jikan.main import app; app(prog_name="jikan")', *args],
            env={**environment, **(env or {})},
            text=True,
            capture_output=True,
            timeout=15,
            check=False,
        )

    return run, tmp_path


def complete(cli, words):
    run, _ = cli
    return run(
        env={
            "_JIKAN_COMPLETE": "complete_bash",
            "COMP_WORDS": words,
            "COMP_CWORD": str(len(words.split()) - 1),
        }
    )


def test_real_completion_protocol_missing_uninitialized_and_dynamic_db(cli):
    run, home = cli
    result = complete(cli, "jikan start --project cli")
    assert result.returncode == 0 and not result.stdout.strip() and not result.stderr
    path = home / ".jikan" / "database.db"
    assert not path.exists()
    with sqlite3.connect(path):
        pass
    result = complete(cli, "jikan start --tag f")
    assert result.returncode == 0 and not result.stdout.strip() and not result.stderr
    assert run("init").returncode == 0
    assert run("project", "add", "--name", "client-web").returncode == 0
    assert run("tag", "add", "--name", "frontend").returncode == 0
    assert run("tag", "add", "--name", "review").returncode == 0
    assert "client-web" in complete(cli, "jikan start --project cli").stdout
    assert "frontend" in complete(cli, "jikan start --tag f").stdout
    assert "review" in complete(cli, "jikan start --tag frontend --tag r").stdout


def test_typer_standard_completion_install_and_command_integration(cli):
    run, home = cli
    # Use Typer's explicit-shell mode: sandboxed CI cannot inspect parent processes.
    result = run(
        "--install-completion", "zsh", env={"_TYPER_COMPLETE_TEST_DISABLE_SHELL_DETECTION": "1"}
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert (home / ".zshrc").exists()
    assert "compinit" in (home / ".zshrc").read_text()
    assert "_JIKAN_COMPLETE" in (home / ".zfunc" / "_jikan").read_text()
    assert run("init").returncode == 0
    result = run("timer")
    assert result.returncode == 0 and "start --title" in result.stdout
    for command in ("list", "report", "export"):
        result = run(command, "--all")
        assert result.returncode == 0, result.stdout + result.stderr
    assert run("export", "--all").stdout.startswith(
        "id,start_at,end_at,duration,title,project,tags"
    )
