import os
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SOURCE_ROOT = PROJECT_ROOT / "src"
FIXED_NOW = "2026-10-21T09:00:00+09:00"


class Cli:
    """Real CLI processes; environment changes are confined to each child."""

    def __init__(self, home: Path):
        self.home = home
        self.home.mkdir()
        script = Path(sys.executable).with_name("jikan")
        self.command = (
            [str(script)]
            if script.exists()
            else [sys.executable, "-c", "from jikan.main import app; app(prog_name='jikan')"]
        )

    def environment(self, *, now=FIXED_NOW, extra=None):
        environment = os.environ.copy()
        for key in tuple(environment):
            if key.startswith(("_JIKAN_COMPLETE", "_TYPER_COMPLETE")):
                environment.pop(key)
        environment.update(
            HOME=str(self.home),
            NO_COLOR="1",
            COLUMNS="200",
            LINES="40",
            TZ="Asia/Tokyo",
            PYTHONPATH=str(SOURCE_ROOT),
        )
        if now is None:
            environment.pop("JIKAN_TEST_NOW", None)
        else:
            environment["JIKAN_TEST_NOW"] = now
        environment.update(extra or {})
        return environment

    def __call__(self, *args, input=None, now=FIXED_NOW, env=None, preserve_newlines=False):
        result = subprocess.run(
            [*self.command, *args],
            cwd=PROJECT_ROOT,
            env=self.environment(now=now, extra=env),
            input=input.encode() if preserve_newlines and input is not None else input,
            text=not preserve_newlines,
            capture_output=True,
            check=False,
            timeout=15,
        )
        if preserve_newlines:
            result.stdout = result.stdout.decode("utf-8")
            result.stderr = result.stderr.decode("utf-8")
        return result


@pytest.fixture()
def cli(tmp_path: Path) -> Cli:
    return Cli(tmp_path / "home")


@pytest.fixture()
def database_path(cli: Cli) -> Path:
    return cli.home / ".jikan" / "database.db"


def query_all(database_path, sql, parameters=()):
    with sqlite3.connect(database_path) as connection:
        connection.row_factory = sqlite3.Row
        return [dict(row) for row in connection.execute(sql, parameters)]


def query_one(database_path, sql, parameters=()):
    rows = query_all(database_path, sql, parameters)
    assert len(rows) == 1
    return rows[0]


def query_value(database_path, sql, parameters=()):
    return next(iter(query_one(database_path, sql, parameters).values()))


def snapshot(database_path):
    """All persisted fields, links and classifications, including SQLite sequences."""
    with sqlite3.connect(database_path) as connection:
        return list(connection.iterdump())


def ok(result):
    assert result.returncode == 0, result.stdout + result.stderr
    return result.stdout


@pytest.fixture()
def classified(cli, database_path):
    ok(cli("init"))
    (database_path.parent / "config.toml").write_text('timezone = "Asia/Tokyo"\n')
    for name in ("client-web", "jikan"):
        ok(cli("project", "add", "--name", name))
    for name in ("development", "frontend", "review"):
        ok(cli("tag", "add", "--name", name))
    return cli
