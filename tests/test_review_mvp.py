"""Independent regressions for diagnostics during CLI module import."""

import csv
import io
import os
import subprocess
import sys
from pathlib import Path

import pytest
from typer.testing import CliRunner

from jikan.core.entry import get_entry, start_time_entry
from jikan.core.project import add_project
from jikan.core.tag import add_tag
from jikan.db import session_context
from jikan.lib import datetime as clock
from jikan.main import app


@pytest.fixture()
def isolated_cli(tmp_path):
    home = tmp_path / "home"
    config_dir = home / ".jikan"
    config_dir.mkdir(parents=True)
    environment = os.environ.copy()
    for name in ("_JIKAN_COMPLETE", "_TYPER_COMPLETE_ARGS", "COMP_WORDS", "COMP_CWORD"):
        environment.pop(name, None)
    environment.update(
        HOME=str(home),
        PYTHONPATH=str(Path(__file__).resolve().parents[1] / "src"),
        JIKAN_TEST_NOW="2026-10-21T09:00:00+09:00",
        TERM="dumb",
        NO_COLOR="1",
    )

    def run(*arguments, code="from jikan.main import app; app(prog_name='jikan')", **extra):
        return subprocess.run(
            [sys.executable, "-c", code, *arguments],
            env={**environment, **extra},
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )

    return run, config_dir


def test_import_config_warning_goes_to_stderr(isolated_cli):
    run, config_dir = isolated_cli
    (config_dir / "config.toml").write_text("timezone = [\n")
    result = run(code="import jikan.main")
    assert result.returncode == 0, result.stderr
    assert result.stdout == ""
    assert "Warning: Invalid syntax" in result.stderr
    assert not (config_dir / "database.db").exists()


def test_export_csv_stays_pure_with_import_time_config_warning(isolated_cli):
    run, config_dir = isolated_cli
    assert run("init").returncode == 0
    (config_dir / "config.toml").write_text("timezone = [\n")
    result = run("export", "--all")
    assert result.returncode == 0, result.stderr
    assert list(csv.reader(io.StringIO(result.stdout))) == [
        ["id", "start_at", "end_at", "duration", "title", "project", "tags"]
    ]
    assert "Warning: Invalid syntax" in result.stderr
    assert "Period: All dates" in result.stderr
    assert "No entries" in result.stderr


@pytest.mark.parametrize("initialized", [False, True])
def test_completion_protocol_survives_import_time_config_warning(isolated_cli, initialized):
    run, config_dir = isolated_cli
    if initialized:
        assert run("init").returncode == 0
        assert run("project", "add", "--name", "client-web").returncode == 0
    completion = {
        "_JIKAN_COMPLETE": "complete_zsh",
        "_TYPER_COMPLETE_ARGS": "jikan start --project cli",
    }
    before = run(**completion)
    (config_dir / "config.toml").write_text("timezone = [\n")
    after = run(**completion)
    assert before.returncode == after.returncode == 0
    assert after.stdout == before.stdout
    assert "Warning: Invalid syntax" in after.stderr
    assert "Warning" not in after.stdout
    if initialized:
        assert "client-web" in after.stdout
    else:
        assert not (config_dir / "database.db").exists()


def _snapshot():
    with session_context() as session:
        return tuple(
            session.connection().exec_driver_sql(f"SELECT * FROM {table} ORDER BY 1, 2").fetchall()
            for table in ("entry", "entrytaglink", "project", "tag")
        )


@pytest.mark.parametrize("option", ["--remove-tag-id", "--remove-tag"])
def test_unknown_removal_id_rolls_back_every_edit(seed_entries, monkeypatch, option):
    monkeypatch.setenv("JIKAN_TEST_NOW", "2030-10-21T09:00:00+09:00")
    add_project("new-project", "")
    before = _snapshot()
    result = CliRunner().invoke(
        app,
        [
            "edit",
            "1",
            "--title",
            "Must rollback",
            "--description",
            "Must rollback",
            "--project",
            "new-project",
            "--tag",
            "tag-2",
            "--remove-tag",
            "tag-1",
            option,
            "999",
        ],
    )
    assert result.exit_code == 1
    assert "999" in result.output and "jikan tag list" in result.output
    assert _snapshot() == before


@pytest.mark.parametrize("arguments", [["--remove-tag", "tag-2"], ["--remove-tag-id", "2"]])
def test_existing_unattached_tag_removal_is_compatible_noop(seed_entries, monkeypatch, arguments):
    monkeypatch.setenv("JIKAN_TEST_NOW", "2030-10-21T09:00:00+09:00")
    result = CliRunner().invoke(app, ["edit", "1", "--title", "Valid edit", *arguments])
    assert result.exit_code == 0, result.output
    assert "Tag not attached" in result.stderr
    after = get_entry(1)
    assert after.title == "Valid edit"
    assert [tag.name for tag in after.tags] == ["tag-1"]


def test_switch_shows_both_stopped_and_started_classification(use_test_engine, monkeypatch):
    monkeypatch.setenv("JIKAN_TEST_NOW", "2026-10-21T09:00:00+09:00")
    for project in ("old-project", "new-project"):
        add_project(project, "")
    for tag in ("old-tag", "new-tag"):
        add_tag(tag)
    start_time_entry(None, "Old task", "", project_name="old-project", tag_names=["old-tag"])
    monkeypatch.setenv("JIKAN_TEST_NOW", "2026-10-21T10:00:00+09:00")
    result = CliRunner().invoke(
        app, ["switch", "--title", "New task", "--project", "new-project", "--tag", "new-tag"]
    )
    assert result.exit_code == 0, result.output
    stopped, started = result.stdout.split("Started #2", 1)
    assert "Stopped #1" in stopped and "Old task" in stopped
    assert "Start at:" in stopped and "Duration: 01h 00m 00s" in stopped
    assert "Project: old-project" in stopped and "Tags: old-tag" in stopped
    assert "New task" in started
    assert "Project: new-project" in started and "Tags: new-tag" in started


def test_view_renders_user_text_literally(use_test_engine, monkeypatch):
    monkeypatch.setenv("JIKAN_TEST_NOW", "2026-10-21T09:00:00+09:00")
    project = "project [/blue]"
    tag = "tag [/green]"
    title, description = "Task [/red]", "Notes [bold]literal[/bold]"
    add_project(project, "")
    add_tag(tag)
    start_time_entry(None, title, description, project_name=project, tag_names=[tag])
    before = _snapshot()
    result = CliRunner().invoke(app, ["view", "1"])
    assert result.exit_code == 0, result.output
    for value in (title, description, project, tag):
        assert value in result.stdout
    assert _snapshot() == before


@pytest.mark.parametrize("timezone", ["", "/invalid/path"])
def test_invalid_timezone_key_cannot_turn_saved_recording_into_failure(
    use_test_engine, monkeypatch, timezone
):
    monkeypatch.setenv("JIKAN_TEST_NOW", "2026-10-21T09:00:00+09:00")
    monkeypatch.setattr(clock.config, "timezone", timezone)
    runner = CliRunner()
    started = runner.invoke(app, ["start", "--title", "First task"])
    assert started.exit_code == 0, started.output
    assert "Timezone UTC is used" in started.stderr
    monkeypatch.setenv("JIKAN_TEST_NOW", "2026-10-21T10:00:00+09:00")
    switched = runner.invoke(app, ["switch", "--title", "Second task"])
    assert switched.exit_code == 0, switched.output
    assert get_entry(1).end_at == get_entry(2).start_at
    edited = runner.invoke(
        app, ["edit", "1", "--start", "2026-10-21 00:10", "--end", "2026-10-21 00:30"]
    )
    assert edited.exit_code == 0, edited.output
    assert "Duration: 00h 20m 00s" in edited.stdout
    assert "Timezone UTC is used" in edited.stderr
    assert "Warning" not in edited.stdout
    assert get_entry(1).start_at.isoformat() == "2026-10-21T00:10:00"
