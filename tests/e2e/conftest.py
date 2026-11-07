import os
import sqlite3
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SOURCE_ROOT = PROJECT_ROOT / "src"
_CLI_BOOTSTRAP = "from jikan.main import app; app()"


@pytest.fixture()
def cli(tmp_path: Path) -> Callable[..., subprocess.CompletedProcess[str]]:
    """Run the Typer application in a fresh process and isolated home directory."""
    home = tmp_path / "home"
    home.mkdir()
    console_script = Path(sys.executable).with_name("jikan")
    command_prefix = (
        [str(console_script)] if console_script.exists() else [sys.executable, "-c", _CLI_BOOTSTRAP]
    )

    def _run(*args: str, input: str | None = None) -> subprocess.CompletedProcess[str]:
        environment = os.environ.copy()
        environment.update(
            {
                "HOME": str(home),
                "NO_COLOR": "1",
                "COLUMNS": "200",
                "LINES": "40",
                "PYTHONPATH": os.pathsep.join(
                    filter(None, [str(SOURCE_ROOT), environment.get("PYTHONPATH")])
                ),
            }
        )
        return subprocess.run(
            [*command_prefix, *args],
            cwd=PROJECT_ROOT,
            env=environment,
            input=input,
            text=True,
            capture_output=True,
            check=False,
        )

    return _run


@pytest.fixture()
def database_path(tmp_path: Path) -> Path:
    return tmp_path / "home" / ".jikan" / "database.db"


def query_one(database_path: Path, sql: str, parameters: tuple[object, ...] = ()) -> sqlite3.Row:
    connection = sqlite3.connect(database_path)
    connection.row_factory = sqlite3.Row
    try:
        row = connection.execute(sql, parameters).fetchone()
        assert row is not None
        return row
    finally:
        connection.close()


def query_value(database_path: Path, sql: str, parameters: tuple[object, ...] = ()) -> object:
    return query_one(database_path, sql, parameters)[0]
