"""LST/RPT/EXP acceptance coverage, isolated from main's ongoing integration."""

import csv
import io
from datetime import UTC, datetime, timedelta
from unittest.mock import Mock
from zoneinfo import ZoneInfo

import pytest
from sqlmodel import select
from typer.testing import CliRunner

from jikan.commands.history import app, export_history, list_history, report_history
from jikan.config import JikanSetting
from jikan.core.query import query_history
from jikan.db import session_context
from jikan.models import Entry, Project, Tag

runner = CliRunner()
NOW = datetime(2026, 10, 21, 3, 0, tzinfo=UTC)  # Noon JST


@pytest.fixture(autouse=True)
def fixed_environment(use_test_engine, monkeypatch):
    monkeypatch.setattr("jikan.lib.datetime.utc_now", lambda: NOW)
    monkeypatch.setattr("jikan.core.query.load_config", lambda: JikanSetting(timezone="Asia/Tokyo"))


@pytest.fixture()
def history():
    with session_context() as session:
        web = Project(name="client-web", archived=True)  # Archived history is still searchable.
        jikan = Project(name="jikan")
        dev, front, review = (Tag(name=name) for name in ("development", "frontend", "review"))
        session.add_all(
            [
                Entry(
                    id=1,
                    title="Build",
                    start_at=NOW - timedelta(hours=3),
                    end_at=NOW - timedelta(hours=2),
                    project=web,
                    tags=[dev, front],
                ),
                Entry(
                    id=2,
                    title="Review",
                    start_at=NOW - timedelta(hours=2),
                    end_at=NOW - timedelta(minutes=90),
                    project=jikan,
                    tags=[review],
                ),
                Entry(id=3, title="Inbox", start_at=NOW - timedelta(minutes=15)),
                Entry(
                    id=4,
                    title="Yesterday",
                    start_at=NOW - timedelta(days=1),
                    end_at=NOW - timedelta(days=1) + timedelta(minutes=10),
                ),
            ]
        )
        session.commit()


def invoke(*args):
    result = runner.invoke(app, list(args))
    assert result.exit_code == 0, (result.output, result.exception)
    return result


def csv_rows(result):
    return list(csv.DictReader(io.StringIO(result.stdout_bytes.decode(), newline="")))


def list_ids(result):
    lines = [line for line in result.stdout.splitlines() if "\t" in line]
    return [int(line.split("\t")[1]) for line in lines[1:]]


def test_list_default_today_states_classification_total_and_read_only(history):
    with session_context() as session:
        before = [entry.model_dump() for entry in session.exec(select(Entry)).all()]
    result = invoke("list")
    assert list_ids(result) == [1, 2, 3]
    assert "Running\t00h 15m 00s\tInbox\tUnassigned\tUnassigned" in result.stdout
    assert "Done\t01h 00m 00s\tBuild\tclient-web\tdevelopment, frontend" in result.stdout
    assert "Total: 01h 45m 00s" in result.stdout
    assert "2026-10-21 to 2026-10-21" in result.stdout
    assert "Asia/Tokyo" in result.stdout
    assert "start_at" in result.stdout and "no clipping" in result.stdout
    assert invoke("list", "--today").stdout == result.stdout
    with session_context() as session:
        assert [entry.model_dump() for entry in session.exec(select(Entry)).all()] == before


@pytest.mark.parametrize(
    "filters, expected",
    [
        (["--all"], [4, 1, 2, 3]),
        (["--project", "client-web"], [1]),
        (["--tag", "review"], [2]),
        (["--tag", "development", "--tag", "frontend"], [1]),
        (["--tag", "development", "--tag", "review"], []),
        (["--tag", "review", "--tag", "review"], [2]),
        (["--project", "jikan", "--tag", "development"], []),
        (["--to", "2026-10-20"], [4]),
        (["--from", "2026-10-21"], [1, 2, 3]),
        (["--from", "2026-10-20", "--to", "2026-10-20"], [4]),
    ],
)
def test_same_filters_for_list_report_and_export(history, filters, expected):
    listed = invoke("list", *filters)
    exported = invoke("export", *filters, "--format", "csv")
    report = invoke("report", *filters)
    assert list_ids(listed) == expected
    assert [int(row["id"]) for row in csv_rows(exported)] == expected
    assert next(line for line in listed.stdout.splitlines() if line.startswith("Total:")) in (
        report.stdout
    )
    assert "Period:" in exported.stderr and "Period:" not in exported.stdout
    assert "Tags (all required / AND)" in listed.stdout


def test_report_exclusive_projects_overlapping_tags_and_unassigned(history):
    result = invoke("report")
    assert "Total: 01h 45m 00s" in result.stdout
    projects, tags = result.stdout.split("By tag", 1)
    assert "client-web  01h 00m 00s" in projects
    assert "jikan  00h 30m 00s" in projects
    assert "Unassigned  00h 15m 00s" in projects
    assert "development  01h 00m 00s" in tags
    assert "frontend  01h 00m 00s" in tags
    assert "review  00h 30m 00s" in tags
    assert "Unassigned  00h 15m 00s" in tags
    assert "overlapping; may not add to Total" in tags
    snapshot = query_history()
    assert sum(snapshot.breakdown().values(), timedelta()) == snapshot.total
    assert sum(snapshot.breakdown(by_tag=True).values(), timedelta()) > snapshot.total


def test_inclusive_month_end_subseconds_and_start_based_whole_duration():
    # UTC naive values are exactly JST midnight and the last microsecond of October.
    with session_context() as session:
        session.add_all(
            [
                Entry(
                    id=1,
                    title="Before",
                    start_at=datetime(2026, 9, 30, 14, 59, 59),
                    end_at=datetime(2026, 10, 1, 1),
                ),
                Entry(
                    id=2,
                    title="First",
                    start_at=datetime(2026, 9, 30, 15),
                    end_at=datetime(2026, 9, 30, 16),
                ),
                Entry(
                    id=3,
                    title="Last",
                    start_at=datetime(2026, 10, 31, 14, 59, 59, 999999),
                    end_at=datetime(2026, 10, 31, 15, 59, 59, 999999),
                ),
                Entry(
                    id=4,
                    title="Next",
                    start_at=datetime(2026, 10, 31, 15),
                    end_at=datetime(2026, 10, 31, 16),
                ),
            ]
        )
        session.commit()
    filters = ["--from", "2026-10-01", "--to", "2026-10-31"]
    assert list_ids(invoke("list", *filters)) == [2, 3]
    assert "Total: 02h 00m 00s" in invoke("report", *filters).stdout
    assert [row["id"] for row in csv_rows(invoke("export", *filters))] == ["2", "3"]


@pytest.mark.parametrize("command", ["list", "report", "export"])
def test_empty_period_is_success_and_csv_is_header_only(command):
    result = invoke(command, "--from", "2026-01-01", "--to", "2026-01-31")
    if command == "export":
        assert result.stdout == "id,start_at,end_at,duration,title,project,tags\n"
        assert "No entries" in result.stderr
        assert "2026-01-01" in result.stderr
    else:
        assert "No entries" in result.stdout
        assert "Total: 00h 00m 00s" in result.stdout
        assert "2026-01-01" in result.stdout


def test_csv_quoting_unicode_blank_running_end_and_long_duration():
    title = '調査,"quote"\nsecond line\r\nthird\rfourth'
    project_name = 'client,"quoted"'
    with session_context() as session:
        session.add(
            Entry(
                id=1,
                title=title,
                start_at=NOW - timedelta(hours=125, seconds=7),
                project=Project(name=project_name),
                tags=[Tag(name='a,"b"'), Tag(name="日本語")],
            )
        )
        session.commit()
    result = invoke("export", "--all")
    rows = csv_rows(result)
    assert len(rows) == 1
    row = rows[0]
    assert list(row) == ["id", "start_at", "end_at", "duration", "title", "project", "tags"]
    assert row["title"] == title
    assert row["project"] == project_name
    assert row["tags"] == 'a,"b",日本語'
    assert row["duration"] == "125:00:07"
    assert row["end_at"] == ""
    assert datetime.fromisoformat(row["start_at"]).utcoffset() == timedelta(hours=9)


def test_csv_stopped_timestamps_are_aware_and_running_uses_clock_once(history, monkeypatch):
    clock = Mock(return_value=NOW)
    monkeypatch.setattr("jikan.lib.datetime.utc_now", clock)
    rows = csv_rows(invoke("export"))
    clock.assert_called_once_with()
    assert rows[0]["duration"] == "01:00:00"
    assert rows[2]["duration"] == "00:15:00"
    assert datetime.fromisoformat(rows[0]["end_at"]).utcoffset() == timedelta(hours=9)


@pytest.mark.parametrize("command", ["list", "report", "export"])
@pytest.mark.parametrize(
    "options, message",
    [
        (["--project", "missing"], "jikan project list"),
        (["--tag", "missing"], "jikan tag list"),
        (["--from", "2026-02-30"], "YYYY-MM-DD"),
        (["--to", "20261021"], "YYYY-MM-DD"),
        (["--from", "2026-10-22", "--to", "2026-10-21"], "on or before"),
        (["--today", "--all"], "one period mode"),
        (["--all", "--from", "2026-10-01"], "one period mode"),
        (["--today", "--to", "2026-10-21"], "one period mode"),
        (["--to", "9999-12-31"], "supported dates"),
    ],
)
def test_invalid_filters_are_errors_without_stdout_or_writes(history, command, options, message):
    result = runner.invoke(app, [command, *options])
    assert result.exit_code == 1
    assert message in result.stderr
    assert result.stdout == ""
    with session_context() as session:
        assert len(session.exec(select(Entry)).all()) == 4
        assert len(session.exec(select(Project)).all()) == 2
        assert len(session.exec(select(Tag)).all()) == 3


def test_unsupported_export_format():
    result = runner.invoke(app, ["export", "--format", "json"])
    assert result.exit_code == 1
    assert result.stdout == ""
    assert "--format csv" in result.stderr


def test_invalid_timezone_is_reported_on_stderr(monkeypatch):
    monkeypatch.setattr(
        "jikan.core.query.load_config", lambda: JikanSetting(timezone="invalid/zone")
    )
    result = runner.invoke(app, ["export"])
    assert result.exit_code == 1
    assert result.stdout == ""
    assert "config.toml" in result.stderr


def test_config_warning_does_not_pollute_csv(monkeypatch):
    def warning_config():
        print("Config warning")
        return JikanSetting()

    monkeypatch.setattr("jikan.core.query.load_config", warning_config)
    result = invoke("export")
    assert result.stdout == "id,start_at,end_at,duration,title,project,tags\n"
    assert "Config warning" in result.stderr


def test_aware_and_naive_return_values_are_normalized(monkeypatch):
    # SQLite returns naive timestamps. Other session factories may preserve offsets.
    entries = [
        Entry(id=1, start_at=datetime(2026, 10, 20, 15), end_at=NOW),
        Entry(
            id=2,
            start_at=datetime(2026, 10, 21, tzinfo=ZoneInfo("Asia/Tokyo")),
            end_at=NOW.astimezone(ZoneInfo("America/New_York")),
        ),
    ]
    monkeypatch.setattr("sqlmodel.Session.exec", lambda *a, **k: Mock(all=lambda: entries))
    result = query_history()
    assert len(result.rows) == 2
    assert result.rows[0].start_at == result.rows[1].start_at
    assert result.rows[0].duration == result.rows[1].duration == timedelta(hours=12)


@pytest.mark.parametrize(
    "day, start, end, hours",
    [
        ("2026-03-08", datetime(2026, 3, 8, 5), datetime(2026, 3, 9, 4), 23),
        ("2026-11-01", datetime(2026, 11, 1, 4), datetime(2026, 11, 2, 5), 25),
    ],
)
def test_configured_timezone_day_boundaries_follow_dst(monkeypatch, day, start, end, hours):
    monkeypatch.setattr(
        "jikan.core.query.load_config", lambda: JikanSetting(timezone="America/New_York")
    )
    with session_context() as session:
        session.add_all(
            [
                Entry(id=1, start_at=start - timedelta(microseconds=1), end_at=start),
                Entry(id=2, start_at=start, end_at=end),
                Entry(id=3, start_at=end, end_at=end + timedelta(seconds=1)),
            ]
        )
        session.commit()
    result = query_history(from_date=day, to_date=day)
    assert [row.id for row in result.rows] == [2]
    assert result.total == timedelta(hours=hours)


def test_default_today_uses_configured_local_date(monkeypatch):
    monkeypatch.setattr(
        "jikan.lib.datetime.utc_now", lambda: datetime(2026, 10, 20, 15, tzinfo=UTC)
    )
    result = query_history()
    assert result.from_date.isoformat() == "2026-10-21"
    assert result.to_date == result.from_date


@pytest.mark.parametrize("running", [False, True])
def test_negative_duration_is_actionable_and_export_writes_no_partial_csv(running):
    with session_context() as session:
        session.add(Entry(id=1, start_at=NOW + timedelta(hours=1), end_at=None if running else NOW))
        session.commit()
    result = runner.invoke(app, ["export", "--all"])
    assert result.exit_code == 1
    assert result.stdout == ""
    assert "jikan edit 1" in result.stderr


def test_callbacks_can_be_registered_on_another_typer_app(history):
    import typer

    root = typer.Typer()
    for name, callback in (
        ("list", list_history),
        ("report", report_history),
        ("export", export_history),
    ):
        root.command(name)(callback)
    result = runner.invoke(root, ["list", "--project", "client-web"])
    assert result.exit_code == 0
    assert list_ids(result) == [1]
