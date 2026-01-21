from datetime import datetime

from pytest_mock import MockFixture
from typer.testing import CliRunner

from jikan.core.entry import (
    EntryAlreadyRunningError,
    EntryNotFoundError,
    EntryNotRunningError,
    running_time,
)
from jikan.lib.datetime import format_timedelta
from jikan.main import app
from jikan.models import Entry

runner = CliRunner()


def test_app():
    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0
    assert "Usage" in result.output


class TestStart:
    def test_success(self, mocker: MockFixture):
        mocker.patch(
            "jikan.main.start_time_entry",
            return_value=Entry(
                id=1, title="Test", description="", project_id=1, start_at=datetime.now()
            ),
        )
        result = runner.invoke(app, ["start", "--id", "1"])

        assert result.exit_code == 0
        assert "Success" in result.output

    def test_with_options(self, mocker: MockFixture):
        mocker.patch(
            "jikan.main.start_time_entry",
            return_value=Entry(
                id=1, title="Test", description="", project_id=1, start_at=datetime.now()
            ),
        )

        result = runner.invoke(
            app, ["start", "--id", "1", "--title", "Test", "--description", "Test"]
        )

        assert result.exit_code == 0
        assert "Success" in result.output

    def test_without_project_id(self, mocker: MockFixture):
        mocker.patch(
            "jikan.main.start_time_entry",
            return_value=Entry(
                id=1, title="Test", description="", project_id=1, start_at=datetime.now()
            ),
        )

        result = runner.invoke(app, ["start", "--title", "Test", "--description", "Test"])

        assert result.exit_code == 2

    def test_core_func_raise_exception(self, mocker: MockFixture):
        mocker.patch(
            "jikan.main.start_time_entry",
            side_effect=Exception(),
        )

        result = runner.invoke(
            app, ["start", "--id", "1", "--title", "Test", "--description", "Test"]
        )

        assert result.exit_code == 1
        assert "Failed to start." in result.output

    def test_fail_if_active_entry_exist(self, mocker: MockFixture):
        mocker.patch(
            "jikan.main.start_time_entry",
            side_effect=EntryAlreadyRunningError(),
        )

        result = runner.invoke(
            app, ["start", "--id", "1", "--title", "Test", "--description", "Test"]
        )

        assert result.exit_code == 1
        assert "Time entry is already running" in result.output


class TestStop:
    def test_with_entry(self, mocker: MockFixture):
        mocker.patch(
            "jikan.main.stop_time_entry",
            return_value=Entry(
                id=1, title="Test", description="", project_id=1, start_at=datetime.now()
            ),
        )
        result = runner.invoke(app, ["stop"])

        assert result.exit_code == 0

    def test_no_entry(self, mocker: MockFixture):
        mocker.patch(
            "jikan.main.stop_time_entry",
            side_effect=EntryNotRunningError(),
        )
        result = runner.invoke(app, ["stop"])

        assert result.exit_code == 1
        assert "No time entry running" in result.output

    def test_with_core_func_raise_exception(self, mocker: MockFixture):
        mocker.patch(
            "jikan.main.stop_time_entry",
            side_effect=Exception(),
        )
        result = runner.invoke(app, ["stop"])

        assert result.exit_code == 1
        assert "Failed to stop." in result.output


class TestStatus:
    def test_entry_running(self, mocker: MockFixture):
        entries = [
            Entry(id=1, project_id=1, title="Test", description="Test", start_at=datetime.now())
        ]
        mocker.patch(
            "jikan.main.get_running_entry",
            return_value=entries,
        )
        result = runner.invoke(app, ["status"])

        assert result.exit_code == 0
        assert entries[0].title in result.output
        assert format_timedelta(running_time(entries[0])) in result.output

    def test_no_entry_running(self, mocker: MockFixture):
        entries = []
        mocker.patch(
            "jikan.main.get_running_entry",
            return_value=entries,
        )
        result = runner.invoke(app, ["status"])

        assert result.exit_code == 0
        assert "No time entry running" in result.output

    def test_multiple_entry_running(self, mocker: MockFixture):
        entries = [
            Entry(id=1, project_id=1, title="Test", description="Test", start_at=datetime.now()),
            Entry(id=2, project_id=1, title="Test", description="Test", start_at=datetime.now()),
        ]
        mocker.patch(
            "jikan.main.get_running_entry",
            return_value=entries,
        )
        result = runner.invoke(app, ["status"])

        assert result.exit_code == 1
        assert "Multiple time entries running" in result.output


class TestList:
    def test_success(self, mocker: MockFixture):
        entries = [
            Entry(id=1, project_id=1, title="Test1", description="Test", start_at=datetime.now()),
            Entry(id=2, project_id=1, title="Test2", description="Test", start_at=datetime.now()),
        ]
        mocker.patch(
            "jikan.main.list_time_entry",
            return_value=entries,
        )
        result = runner.invoke(app, ["list"])

        assert result.exit_code == 0
        assert "Title" in result.output
        assert "Test1" in result.output
        assert "Test2" in result.output

    def test_no_entry(self, mocker: MockFixture):
        entries = []
        mocker.patch(
            "jikan.main.list_time_entry",
            return_value=entries,
        )
        result = runner.invoke(app, ["list"])

        assert result.exit_code == 0
        assert "Title" in result.output


class TestEdit:
    def test_success(self, mocker: MockFixture):
        mocker.patch(
            "jikan.main.get_entry",
            return_value=Entry(
                id=1, project_id=1, title="Entry", description="Entry", start_at=datetime.now()
            ),
        )
        mocker.patch(
            "jikan.main.edit_entry",
            return_value=Entry(
                id=1, project_id=1, title="Edited", description="Edited", start_at=datetime.now()
            ),
        )

        result = runner.invoke(
            app, ["edit", "--id", "1", "--title", "Edited", "--description", "Edited"]
        )

        assert result.exit_code == 0
        assert "Entry edited" in result.output
        assert "Success" in result.output

    def test_id_not_passed(self):
        result = runner.invoke(app, ["edit", "--title", "Entry", "--description", "Entry"])

        assert result.exit_code == 2

    def test_title_or_description_should_be_passed(self):
        result = runner.invoke(app, ["edit", "--id", "1"])

        assert result.exit_code == 1

    def test_entry_not_found(self, mocker: MockFixture):
        mocker.patch(
            "jikan.main.get_entry",
            side_effect=EntryNotFoundError(),
        )

        result = runner.invoke(
            app, ["edit", "--id", "1", "--title", "Edited", "--description", "Edited"]
        )
        assert result.exit_code == 1


class TestDelete:
    def test_success(self, mocker: MockFixture):
        mocker.patch(
            "jikan.main.get_entry",
            return_value=Entry(
                id=1, project_id=1, title="Entry", description="Entry", start_at=datetime.now()
            ),
        )
        mocker.patch("jikan.main.typer.confirm", return_value=True)
        mocker.patch(
            "jikan.main.delete_entry",
            return_value=None,
        )

        result = runner.invoke(app, ["delete", "--id", "1"])
        assert result.exit_code == 0
        assert "Entry deleted" in result.output

    def test_id_not_passed(self):
        result = runner.invoke(app, ["delete"])
        assert result.exit_code == 2

    def test_entry_not_found(self, mocker: MockFixture):
        mocker.patch(
            "jikan.main.get_entry",
            side_effect=EntryNotFoundError(),
        )
        result = runner.invoke(app, ["delete", "--id", "1"])
        assert result.exit_code == 1

    def test_reject_confirmation(self, mocker: MockFixture):
        mocker.patch(
            "jikan.main.get_entry",
            side_effect=EntryNotFoundError(),
        )
        mocker.patch("jikan.main.typer.confirm", return_value=False)

        result = runner.invoke(app, ["delete", "--id", "1"])
        assert result.exit_code == 1
