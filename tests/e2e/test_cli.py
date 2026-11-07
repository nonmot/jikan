import subprocess
from collections.abc import Callable
from pathlib import Path

from .conftest import query_one, query_value

Cli = Callable[..., subprocess.CompletedProcess[str]]


def initialize(cli: Cli) -> None:
    result = cli("init")
    assert result.returncode == 0, result.stdout + result.stderr


def add_project(cli: Cli, name: str = "client-web") -> None:
    result = cli("project", "add", "--name", name, "--description", "Web application")
    assert result.returncode == 0, result.stdout + result.stderr


def add_tag(cli: Cli, name: str) -> None:
    result = cli("tag", "add", "--name", name)
    assert result.returncode == 0, result.stdout + result.stderr


def test_initialization_and_classification_lifecycle(cli: Cli, database_path: Path):
    initialize(cli)

    assert database_path.exists()
    assert query_value(database_path, "SELECT COUNT(*) FROM entry") == 0

    add_project(cli)
    project_list = cli("project", "list")
    assert project_list.returncode == 0
    assert "client-web" in project_list.stdout

    project_view = cli("project", "view", "1")
    assert project_view.returncode == 0
    assert "Name: client-web" in project_view.stdout
    assert "Archived: False" in project_view.stdout

    assert cli("project", "edit", "1", "--name", "client-portal").returncode == 0
    assert cli("project", "archive", "1").returncode == 0
    assert "client-portal" not in cli("project", "list").stdout
    assert cli("project", "unarchive", "1").returncode == 0
    assert "client-portal" in cli("project", "list").stdout

    add_tag(cli, "frontend")
    assert "frontend" in cli("tag", "list").stdout
    assert cli("tag", "edit", "1", "--name", "ui").returncode == 0
    assert "ui" in cli("tag", "list").stdout


def test_start_status_and_duplicate_start_preserve_single_running_entry(
    cli: Cli, database_path: Path
):
    initialize(cli)
    add_project(cli)

    started = cli(
        "start",
        "--id",
        "1",
        "--title",
        "ログイン画面の実装",
        "--description",
        "フォーム実装",
    )
    assert started.returncode == 0
    assert "Time entry started at" in started.stdout

    status = cli("status")
    assert status.returncode == 0
    for expected in ("ID: 1", "Title: ログイン画面の実装", "Project: client-web"):
        assert expected in status.stdout

    running_before = query_one(database_path, "SELECT id, title, start_at, end_at FROM entry")
    assert running_before["end_at"] is None

    duplicate = cli("start", "--title", "別の作業")
    assert duplicate.returncode == 1
    assert "Time entry is already running" in duplicate.stdout
    assert query_value(database_path, "SELECT COUNT(*) FROM entry") == 1
    running_after = query_one(database_path, "SELECT id, title, start_at, end_at FROM entry")
    assert dict(running_after) == dict(running_before)


def test_status_and_stop_when_no_entry_is_running(cli: Cli, database_path: Path):
    initialize(cli)

    status = cli("status")
    assert status.returncode == 0
    assert "No time entry running." in status.stdout

    stopped = cli("stop")
    assert stopped.returncode == 1
    assert "No time entry running" in stopped.stdout
    assert query_value(database_path, "SELECT COUNT(*) FROM entry") == 0


def test_stop_list_view_and_edit_an_entry(cli: Cli, database_path: Path):
    initialize(cli)
    add_project(cli)
    add_tag(cli, "frontend")
    add_tag(cli, "review")
    assert cli("start", "--title", "Initial task").returncode == 0

    stopped = cli("stop")
    assert stopped.returncode == 0
    assert "Time entry stopped at" in stopped.stdout
    stopped_entry = query_one(database_path, "SELECT start_at, end_at FROM entry WHERE id = 1")
    assert stopped_entry["end_at"] is not None

    edited = cli(
        "edit",
        "1",
        "--title",
        "Edited task",
        "--description",
        "Updated description",
        "--start",
        "2026/01/01 09:00:00",
        "--end",
        "2026/01/01 10:30:00",
        "--project",
        "1",
        "--add-tag",
        "1",
        "--add-tag",
        "2",
        "--remove-tag",
        "1",
    )
    assert edited.returncode == 0, edited.stdout + edited.stderr
    assert "Entry edited" in edited.stdout

    entry = query_one(
        database_path,
        "SELECT title, description, project_id, start_at, end_at FROM entry WHERE id = 1",
    )
    assert dict(entry) == {
        "title": "Edited task",
        "description": "Updated description",
        "project_id": 1,
        "start_at": "2026-01-01 09:00:00.000000",
        "end_at": "2026-01-01 10:30:00.000000",
    }

    listed = cli("list")
    assert listed.returncode == 0
    assert "Edited task" in listed.stdout
    viewed = cli("view", "1")
    assert viewed.returncode == 0
    assert "Duration: 01h 30m 00s" in viewed.stdout
    assert "Project: client-web" in viewed.stdout
    assert "Tags: review" in viewed.stdout


def test_invalid_time_edit_leaves_entry_unchanged(cli: Cli, database_path: Path):
    initialize(cli)
    assert cli("start", "--title", "Task").returncode == 0
    assert cli("stop").returncode == 0
    before = query_one(database_path, "SELECT start_at, end_at FROM entry WHERE id = 1")

    invalid = cli(
        "edit",
        "1",
        "--start",
        "2026/01/01 11:00:00",
        "--end",
        "2026/01/01 10:00:00",
    )
    assert invalid.returncode == 1
    assert "Start time must be before or equal to end time" in invalid.stdout
    after = query_one(database_path, "SELECT start_at, end_at FROM entry WHERE id = 1")
    assert dict(after) == dict(before)


def test_confirmed_deletions_remove_entries_projects_and_tags(cli: Cli, database_path: Path):
    initialize(cli)
    add_project(cli)
    add_tag(cli, "frontend")
    assert cli("start", "--id", "1", "--title", "Disposable").returncode == 0
    assert cli("stop").returncode == 0

    cancelled_tag_deletion = cli("tag", "delete", "1", input="n\n")
    assert cancelled_tag_deletion.returncode == 1
    assert query_value(database_path, "SELECT COUNT(*) FROM tag") == 1

    deleted_entry = cli("delete", "1", input="y\n")
    assert deleted_entry.returncode == 0
    assert query_value(database_path, "SELECT COUNT(*) FROM entry") == 0
    assert cli("view", "1").returncode == 1

    deleted_tag = cli("tag", "delete", "1", input="y\n")
    assert deleted_tag.returncode == 0
    assert query_value(database_path, "SELECT COUNT(*) FROM tag") == 0

    deleted_project = cli("project", "delete", "1", input="y\n")
    assert deleted_project.returncode == 0
    assert query_value(database_path, "SELECT COUNT(*) FROM project") == 0
