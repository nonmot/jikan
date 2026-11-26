"""LST/EDT/RPT/EXP through the public entry point, without feature mocks."""

import csv
import io
from datetime import datetime, timedelta

import pytest

from .conftest import ok, query_one, snapshot

HEADER = "id,start_at,end_at,duration,title,project,tags\n"


def rows(result):
    ok(result)
    reader = csv.DictReader(io.StringIO(result.stdout, newline=""))
    assert reader.fieldnames == HEADER.strip().split(",")
    return list(reader)


def list_ids(output):
    # Read the documented ID column, not title substrings (which can overlap).
    lines = [line.split("\t") for line in output.splitlines() if "\t" in line]
    assert lines[0][:3] == ["Date", "ID", "Status"]
    return [int(line[1]) for line in lines[1:]]


def record(cli, title, start, end=None, *classification):
    ok(cli("start", "--title", title, *classification, now=start))
    if end:
        ok(cli("stop", now=end))


@pytest.fixture()
def history(classified):
    cli = classified
    record(
        cli,
        "Build",
        "2026-10-21T06:00:00+09:00",
        "2026-10-21T07:00:00+09:00",
        "--project",
        "client-web",
        "--tag",
        "development",
        "--tag",
        "frontend",
    )
    record(
        cli,
        "Review",
        "2026-10-21T07:00:00+09:00",
        "2026-10-21T07:30:00+09:00",
        "--project",
        "jikan",
        "--tag",
        "review",
    )
    record(cli, "Yesterday", "2026-10-20T09:00:00+09:00", "2026-10-20T09:10:00+09:00")
    record(cli, "Inbox", "2026-10-21T08:45:00+09:00")
    return cli


@pytest.mark.parametrize(
    "filters, expected, total",
    [
        ([], [1, 2, 4], "01h 45m 00s"),
        (["--today"], [1, 2, 4], "01h 45m 00s"),
        (["--all"], [3, 1, 2, 4], "01h 55m 00s"),
        (["--from", "2026-10-20", "--to", "2026-10-20"], [3], "00h 10m 00s"),
        (["--from", "2026-10-21"], [1, 2, 4], "01h 45m 00s"),
        (["--to", "2026-10-20"], [3], "00h 10m 00s"),
        (["--project", "client-web"], [1], "01h 00m 00s"),
        (["--tag", "review"], [2], "00h 30m 00s"),
        (["--tag", "development", "--tag", "frontend"], [1], "01h 00m 00s"),
        (["--tag", "development", "--tag", "review"], [], "00h 00m 00s"),
        (["--project", "jikan", "--tag", "development"], [], "00h 00m 00s"),
    ],
)
def test_lst_01_exp_01_same_filters_and_totals(history, database_path, filters, expected, total):
    before = snapshot(database_path)
    listed = ok(history("list", *filters))
    assert list_ids(listed) == expected
    assert f"Total: {total}" in listed
    assert "Asia/Tokyo" in listed
    if not filters:
        for text in (
            "Running\t00h 15m 00s\tInbox\tUnassigned\tUnassigned",
            "Done\t01h 00m 00s\tBuild\tclient-web\tdevelopment, frontend",
        ):
            assert text in listed
    report = ok(history("report", *filters))
    assert f"Total: {total}" in report
    exported = history("export", *filters, "--format", "csv")
    assert [int(row["id"]) for row in rows(exported)] == expected
    assert "Period:" not in exported.stdout and "Period:" in exported.stderr
    if not expected:
        assert exported.stdout == HEADER
        assert "No entries" in exported.stderr
    assert snapshot(database_path) == before


def test_rpt_01_105_minutes_exclusive_projects_overlapping_tags(history, database_path):
    ok(history("stop"))  # Three completed entries: 60 + 30 + 15 minutes.
    before = snapshot(database_path)
    out = ok(history("report", "--from", "2026-10-21", "--to", "2026-10-21"))
    projects, tags = out.split("By tag", 1)
    assert "Total: 01h 45m 00s" in projects
    for name, duration in (
        ("client-web", "01h 00m 00s"),
        ("jikan", "00h 30m 00s"),
        ("Unassigned", "00h 15m 00s"),
    ):
        assert f"{name}  {duration}" in projects
    for name, duration in (
        ("development", "01h 00m 00s"),
        ("frontend", "01h 00m 00s"),
        ("review", "00h 30m 00s"),
        ("Unassigned", "00h 15m 00s"),
    ):
        assert f"{name}  {duration}" in tags
    assert "overlapping" in tags and "Total" in tags
    assert snapshot(database_path) == before


def test_rpt_02_tz_month_boundary_whole_duration_and_empty(classified, database_path):
    cli = classified
    # UTC dates differ from configured JST. A crossing entry counts in full at its start date.
    for title, start, end in (
        ("Before", "2026-09-30T14:59:59+00:00", "2026-09-30T16:00:00+00:00"),
        ("First", "2026-09-30T15:00:00+00:00", "2026-09-30T16:00:00+00:00"),
        ("Last", "2026-10-31T14:59:59+00:00", "2026-10-31T15:59:59+00:00"),
        ("Next", "2026-10-31T15:00:00+00:00", "2026-10-31T16:00:00+00:00"),
    ):
        record(cli, title, start, end)
    before = snapshot(database_path)
    filters = ("--from", "2026-10-01", "--to", "2026-10-31")
    assert list_ids(ok(cli("list", *filters))) == [2, 3]
    out = ok(cli("report", *filters))
    assert "02h 00m 00s" in out
    assert all(value in out for value in ("2026-10-01", "2026-10-31", "Asia/Tokyo"))
    assert [row["title"] for row in rows(cli("export", *filters))] == ["First", "Last"]
    for command in ("list", "report", "export"):
        result = cli(command, "--from", "2025-01-01", "--to", "2025-01-31")
        ok(result)
        if command == "export":
            assert result.stdout == HEADER
            assert "No entries" in result.stderr and "2025-01-01" in result.stderr
        else:
            assert "No entries" in result.stdout and "00h 00m 00s" in result.stdout
    assert snapshot(database_path) == before


def test_rpt_02_respects_nondefault_configured_timezone(classified, database_path):
    cli = classified
    (database_path.parent / "config.toml").write_text('timezone = "America/New_York"\n')
    record(cli, "NY September", "2026-10-01T03:59:59+00:00", "2026-10-01T04:59:59+00:00")
    record(cli, "NY October", "2026-10-01T04:00:00+00:00", "2026-10-01T05:00:00+00:00")
    filters = ("--from", "2026-09-01", "--to", "2026-09-30")
    assert list_ids(ok(cli("list", *filters))) == [1]
    report = ok(cli("report", *filters))
    assert "America/New_York" in report and "01h 00m 00s" in report
    assert [row["title"] for row in rows(cli("export", *filters))] == ["NY September"]


def test_exp_01_csv_quoting_aware_timestamps_and_pure_stdout(classified, database_path):
    cli = classified
    title = '調査,"quoted"\nsecond line\r\nthird\rfourth'
    project = 'client,"quoted"'
    tag = 'tag,"quoted"'
    ok(cli("project", "add", "--name", project))
    ok(cli("tag", "add", "--name", tag))
    record(
        cli,
        title,
        "2026-10-21T07:00:00+09:00",
        "2026-10-21T08:00:00+09:00",
        "--project",
        project,
        "--tag",
        tag,
        "--tag",
        "frontend",
    )
    before = snapshot(database_path)
    result = cli("export", "--format", "csv", preserve_newlines=True)
    exported = rows(result)
    assert len(exported) == 1
    row = exported[0]
    assert row["title"] == title
    assert row["project"] == project
    assert tag in row["tags"] and "frontend" in row["tags"]
    assert row["duration"] == "01:00:00"
    for field in ("start_at", "end_at"):
        assert datetime.fromisoformat(row[field]).utcoffset() == timedelta(hours=9)
    assert result.stdout.startswith(HEADER.strip())
    assert '""quoted""' in result.stdout
    assert snapshot(database_path) == before


def test_edt_01_named_and_legacy_edit(classified, database_path):
    cli = classified
    record(
        cli,
        "Initial",
        "2026-10-21T06:00:00+09:00",
        "2026-10-21T07:00:00+09:00",
        "--project",
        "client-web",
        "--tag",
        "frontend",
    )
    out = ok(
        cli(
            "edit",
            "1",
            "--title",
            "Edited",
            "--description",
            "Updated",
            "--start",
            "2026/10/21 09:30:00",
            "--end",
            "2026/10/21 11:00:00",
            "--project",
            "jikan",
            "--tag",
            "review",
            "--remove-tag",
            "frontend",
        )
    )
    assert "Edited" in out and "jikan" in out and "review" in out
    entry = query_one(database_path, "SELECT * FROM entry")
    assert entry["title"] == "Edited" and entry["description"] == "Updated"
    assert entry["project_id"] == 2
    assert entry["start_at"] == "2026-10-21 00:30:00.000000"
    assert entry["end_at"] == "2026-10-21 02:00:00.000000"
    for command in (("view", "1"), ("list", "--all")):
        out = ok(cli(*command))
        assert "Edited" in out and "jikan" in out and "review" in out
        assert "frontend" not in out
    ok(cli("edit", "1", "--project-id", "1", "--add-tag", "1", "--remove-tag-id", "3"))
    out = ok(cli("view", "1"))
    assert "client-web" in out and "development" in out and "review" not in out
    ok(cli("start", "--id", "2", "--title", "Legacy"))
    assert query_one(database_path, "SELECT * FROM entry WHERE id=2")["project_id"] == 2


@pytest.mark.parametrize(
    "changes, reason",
    [
        (["--start", "2026/10/21 02:00:00", "--end", "2026/10/21 01:00:00"], "time"),
        (["--tag", "missing-tag"], "missing-tag"),
        (["--project", "missing-project"], "missing-project"),
        (["--add-tag", "9999"], "9999"),
    ],
)
def test_edt_02_all_fields_and_links_unchanged(classified, database_path, changes, reason):
    cli = classified
    record(
        cli,
        "Original",
        "2026-10-21T06:00:00+09:00",
        "2026-10-21T07:00:00+09:00",
        "--project",
        "client-web",
        "--tag",
        "frontend",
    )
    before = snapshot(database_path)
    result = cli(
        "edit",
        "1",
        "--title",
        "Must rollback",
        "--description",
        "Also rollback",
        "--remove-tag",
        "frontend",
        *changes,
    )
    assert result.returncode != 0
    assert reason.lower() in (result.stdout + result.stderr).lower()
    assert snapshot(database_path) == before


@pytest.mark.parametrize("command", ["list", "report", "export"])
@pytest.mark.parametrize(
    "filters",
    [
        ["--today", "--all"],
        ["--from", "2026-02-30"],
        ["--from", "2026-10-22", "--to", "2026-10-21"],
        ["--tag", "missing"],
    ],
)
def test_invalid_filters_preserve_database(history, database_path, command, filters):
    before = snapshot(database_path)
    result = history(command, *filters)
    assert result.returncode != 0
    assert result.stdout == "" and result.stderr
    assert snapshot(database_path) == before
