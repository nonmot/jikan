from pytest_mock import MockFixture
from typer import Abort
from typer.testing import CliRunner

from jikan.core.tag import TagNotFoundError
from jikan.main import app
from jikan.models import Tag

runner = CliRunner()


class TestTagList:
    def test_success(self, mocker: MockFixture):
        mocker.patch("jikan.commands.tag.list_tag", return_value=[Tag(name="Mock Tag")])
        result = runner.invoke(app, ["tag", "list"])

        assert result.exit_code == 0
        assert "ID" in result.output
        assert "Name" in result.output

    def test_without_tag(self, mocker: MockFixture):
        mocker.patch(
            "jikan.commands.tag.list_tag",
            return_value=[],
        )
        result = runner.invoke(app, ["tag", "list"])

        assert result.exit_code == 0
        assert "ID" in result.output
        assert "Name" in result.output


class TestTagAdd:
    @staticmethod
    def mock_tag_add(name: str) -> Tag:
        return Tag(name=name)

    def test_success(self, mocker: MockFixture):
        mocker.patch("jikan.commands.tag.add_tag", side_effect=self.mock_tag_add)
        result = runner.invoke(app, ["tag", "add", "--name", "Test"])

        assert result.exit_code == 0
        assert "Success" in result.output
        assert "Tag created. name: Test" in result.output

    def test_name_should_be_given(self):
        result = runner.invoke(app, ["tag", "add"])

        assert result.exit_code == 2

    def test_name_should_not_be_empty(self):
        result = runner.invoke(app, ["tag", "add", "--name"])

        assert result.exit_code == 2


class TestTagEdit:
    def test_success(self, mocker: MockFixture):
        mocker.patch(
            "jikan.commands.tag.get_tag",
            return_value=Tag(name="Test"),
        )
        mocker.patch(
            "jikan.commands.tag.edit_tag",
            return_value=Tag(name="Edited"),
        )
        result = runner.invoke(app, ["tag", "edit", "--id", "1", "--name", "Edited"])

        assert result.exit_code == 0
        assert "Success" in result.output

    def test_name_should_be_given(self):
        result = runner.invoke(app, ["tag", "edit", "--id", "1", "--name"])
        assert result.exit_code == 2

    def test_id_should_be_given(self):
        result = runner.invoke(app, ["tag", "edit", "--id", "--name", "Edited"])
        assert result.exit_code == 2

    def test_tag_not_found(self, mocker: MockFixture):
        mocker.patch(
            "jikan.commands.tag.get_tag",
            side_effect=TagNotFoundError(),
        )
        result = runner.invoke(app, ["tag", "edit", "--id", "1", "--name", "Edited"])
        assert result.exit_code == 1
        assert "Tag not found" in result.output


class TestTagDelete:
    def test_success(self, mocker: MockFixture):
        mocker.patch(
            "jikan.commands.tag.get_tag",
            return_value=Tag(name="Test"),
        )
        mocker.patch("jikan.commands.tag.typer.confirm", return_value=True)
        mocker.patch("jikan.commands.tag.delete_tag", return_value=None)
        result = runner.invoke(app, ["tag", "delete", "--id", "1"])

        assert result.exit_code == 0
        assert "Success" in result.output

    def test_id_should_be_given(self):
        result = runner.invoke(app, ["tag", "delete", "--id"])

        assert result.exit_code == 2

    def test_tag_not_found(self, mocker: MockFixture):
        mocker.patch(
            "jikan.commands.tag.get_tag",
            side_effect=TagNotFoundError(),
        )
        result = runner.invoke(app, ["tag", "delete", "--id", "1"])

        assert result.exit_code == 1
        assert "Tag not found" in result.output

    def test_confirm_cancel(self, mocker: MockFixture):
        mocker.patch(
            "jikan.commands.tag.get_tag",
            return_value=Tag(name="Test"),
        )
        mocker.patch("jikan.commands.tag.typer.confirm", side_effect=Abort)
        result = runner.invoke(app, ["tag", "delete", "--id", "1"])

        assert result.exit_code == 1
