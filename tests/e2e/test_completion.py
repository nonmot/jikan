"""CMP-01: invoke the same completion protocol used by generated shell scripts."""

import re

import pytest

from .conftest import snapshot


def complete(cli, words):
    return cli(env={"_JIKAN_COMPLETE": "complete_zsh", "_TYPER_COMPLETE_ARGS": words})


@pytest.mark.parametrize(
    "words, expected, excluded",
    [
        ("jikan start --project cli", "client-web", "jikan"),
        ("jikan start --project client-web --tag f", "frontend", "review"),
        ("jikan start --tag development --tag frontend --tag r", "review", "frontend"),
        ("jikan switch --project ji", "jikan", "client-web"),
        ("jikan edit 1 --tag f", "frontend", "development"),
        ("jikan edit 1 --remove-tag r", "review", "frontend"),
    ],
)
def test_cmp_01_dynamic_protocol(classified, database_path, words, expected, excluded):
    before = snapshot(database_path)
    result = complete(classified, words)
    assert result.returncode == 0, result.stderr
    # Candidate strings are quoted inside Zsh's _arguments wrapper.
    candidates = re.findall(r'"([^"\n]+)"', result.stdout)
    assert expected in candidates
    assert excluded not in candidates
    assert "Traceback" not in result.stderr
    assert snapshot(database_path) == before


def test_cmp_01_missing_database_and_no_candidates_are_safe(cli, database_path):
    for words in (
        "jikan start --project cli",
        "jikan start --tag r",
        "jikan start --tag frontend --tag missing",
    ):
        result = complete(cli, words)
        assert result.returncode == 0, result.stdout + result.stderr
        assert "Traceback" not in result.stdout + result.stderr
        assert not database_path.exists()


def test_cmp_01_empty_candidates_and_protocol_script(classified, database_path):
    before = snapshot(database_path)
    result = classified(
        "--show-completion", "zsh", env={"_TYPER_COMPLETE_TEST_DISABLE_SHELL_DETECTION": "1"}
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "_JIKAN_COMPLETE=complete_zsh" in result.stdout
    assert "_TYPER_COMPLETE_ARGS" in result.stdout
    result = complete(classified, "jikan start --tag no-such-prefix")
    assert result.returncode == 0 and "Traceback" not in result.stdout + result.stderr
    assert "development" not in result.stdout and "frontend" not in result.stdout
    assert snapshot(database_path) == before
