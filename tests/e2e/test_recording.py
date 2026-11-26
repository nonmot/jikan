"""SET/STR/SWT/STS/STP: subprocess output and complete SQLite state."""

from datetime import UTC, datetime

import pytest

from .conftest import ok, query_all, query_one, query_value, snapshot


def instant(value):
    parsed = datetime.fromisoformat(value)
    return parsed.replace(tzinfo=UTC) if parsed.tzinfo is None else parsed.astimezone(UTC)


def test_set_01(classified, database_path):
    cli = classified
    assert query_value(database_path, "SELECT COUNT(*) FROM entry") == 0
    for name in ("client-web", "jikan"):
        assert name in ok(cli("project", "list"))
    for name in ("development", "frontend", "review"):
        assert name in ok(cli("tag", "list"))
    assert len(query_all(database_path, "SELECT * FROM project")) == 2
    assert len(query_all(database_path, "SELECT * FROM tag")) == 3


def test_str_01_sts_01_stp_01(classified, database_path):
    cli = classified
    out = ok(
        cli(
            "start",
            "--title",
            "ログイン画面の実装",
            "--project",
            "client-web",
            "--tag",
            "development",
            "--tag",
            "frontend",
        )
    )
    for text in (
        "1",
        "ログイン画面の実装",
        "client-web",
        "development",
        "frontend",
        "2026-10-21 09:00:00",
    ):
        assert text in out
    entry = query_one(database_path, "SELECT * FROM entry")
    assert entry["end_at"] is None and entry["project_id"] == 1
    assert instant(entry["start_at"]) == datetime(2026, 10, 21, tzinfo=UTC)
    assert query_all(
        database_path,
        "SELECT tag.name FROM tag JOIN entrytaglink "
        "ON tag.id = entrytaglink.tag_id ORDER BY tag.name",
    ) == [{"name": "development"}, {"name": "frontend"}]
    before = snapshot(database_path)
    status = ok(cli("status", now="2026-10-21T09:42:18+09:00"))
    for text in (
        "Title:",
        "ログイン画面の実装",
        "client-web",
        "development",
        "frontend",
        "2026-10-21 09:00:00",
        "00h 42m 18s",
    ):
        assert text in status
    assert snapshot(database_path) == before
    stopped = ok(cli("stop", now="2026-10-21T09:42:18+09:00"))
    for text in ("ログイン画面の実装", "2026-10-21 09:42:18", "00h 42m 18s"):
        assert text in stopped
    entry = query_one(database_path, "SELECT * FROM entry")
    assert instant(entry["end_at"]) == datetime(2026, 10, 21, 0, 42, 18, tzinfo=UTC)
    assert "No time entry running" in ok(cli("status"))


def test_str_02_sts_02_stp_02(classified, database_path):
    cli = classified
    out = ok(cli("status"))
    assert "No time entry running" in out and "start --title" in out
    out = ok(cli("start", "--title", "メール整理"))
    assert "Unassigned" in out
    entry = query_one(database_path, "SELECT * FROM entry")
    assert entry["project_id"] is None and entry["end_at"] is None
    assert query_value(database_path, "SELECT COUNT(*) FROM entrytaglink") == 0
    ok(cli("stop", now="2026-10-21T09:15:00+09:00"))
    before = snapshot(database_path)
    result = cli("stop")
    assert result.returncode != 0
    assert "No time entry running" in result.stdout and "status" in result.stdout
    assert snapshot(database_path) == before


@pytest.mark.parametrize("command", ["start", "switch"])
@pytest.mark.parametrize("option, recovery", [("--project", "project"), ("--tag", "tag")])
@pytest.mark.parametrize("running", [False, True])
def test_str_03_swt_03_invalid_classification_is_atomic(
    classified, database_path, command, option, recovery, running
):
    cli = classified
    if running:
        ok(cli("start", "--title", "Original", "--project", "client-web", "--tag", "frontend"))
    before = snapshot(database_path)
    result = cli(command, "--title", "Rejected", option, "missing-classification")
    assert result.returncode != 0
    out = result.stdout + result.stderr
    # A duplicate start may reject before resolving classification; it still must be atomic.
    if not (running and command == "start"):
        assert "missing-classification" in out and f"jikan {recovery}" in out
    assert snapshot(database_path) == before


def test_str_04_swt_01(classified, database_path):
    cli = classified
    ok(cli("start", "--title", "Original", "--project", "client-web", "--tag", "frontend"))
    before = snapshot(database_path)
    rejected = cli("start", "--title", "Duplicate")
    assert rejected.returncode != 0
    for text in ("Original", "2026-10-21 09:00:00", "client-web", "switch", "stop"):
        assert text in rejected.stdout
    assert snapshot(database_path) == before
    out = ok(
        cli(
            "switch",
            "--title",
            "Review",
            "--project",
            "jikan",
            "--tag",
            "review",
            now="2026-10-21T09:42:18+09:00",
        )
    )
    assert "Original" in out and "Review" in out and "00h 42m 18s" in out
    entries = query_all(database_path, "SELECT * FROM entry ORDER BY id")
    assert len(entries) == 2
    assert entries[0]["end_at"] == entries[1]["start_at"]
    assert instant(entries[1]["start_at"]) == datetime(2026, 10, 21, 0, 42, 18, tzinfo=UTC)
    assert entries[1]["end_at"] is None and entries[1]["project_id"] == 2
    assert query_value(database_path, "SELECT COUNT(*) FROM entry WHERE end_at IS NULL") == 1
    assert query_all(database_path, "SELECT tag_id FROM entrytaglink WHERE entry_id=2") == [
        {"tag_id": 3}
    ]


def test_swt_02(classified, database_path):
    out = ok(classified("switch", "--title", "Fresh", "--project", "jikan", "--tag", "review"))
    assert "No time entry running" in out and "Fresh" in out
    entry = query_one(database_path, "SELECT * FROM entry")
    assert entry["end_at"] is None and entry["project_id"] == 2


@pytest.mark.parametrize("command", ["start", "switch", "stop", "status", "timer"])
def test_multiple_running_is_detected_without_mutation(classified, database_path, command):
    cli = classified
    ok(cli("start", "--title", "Original"))
    import sqlite3

    with sqlite3.connect(database_path) as connection:
        connection.execute(
            "INSERT INTO entry (title,start_at,created_at,updated_at) "
            "SELECT 'Corrupt duplicate',start_at,created_at,updated_at FROM entry"
        )
    before = snapshot(database_path)
    result = cli(command)
    assert result.returncode != 0
    assert "multiple" in (result.stdout + result.stderr).lower()
    assert snapshot(database_path) == before
