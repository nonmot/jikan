from pytest_mock import MockFixture
from typer import Abort
from typer.testing import CliRunner

from jikan.core.project import ProjectNotFoundError
from jikan.main import app
from jikan.models import Project

runner = CliRunner()


class TestProjectList:
    def test_project_list(self, mocker: MockFixture):
        mocker.patch(
            "jikan.commands.project.list_project",
            return_value=[Project(name="Mock Project", description="This is a mock test")],
        )
        result = runner.invoke(app, ["project", "list"])

        assert result.exit_code == 0
        assert "ID" in result.output
        assert "Name" in result.output
        assert "Description" in result.output
        assert "Mock" in result.output
        assert "This is a mock test" in result.output

    def test_with_no_project(self, mocker: MockFixture):
        mocker.patch(
            "jikan.commands.project.list_project",
            return_value=[],
        )
        result = runner.invoke(app, ["project", "list"])

        assert result.exit_code == 0
        assert "ID" in result.output
        assert "Name" in result.output
        assert "Description" in result.output


class TestProjectAdd:
    @staticmethod
    def mock_project_add(name: str, description: str) -> Project:
        return Project(name=name, description=description)

    def test_success(self, mocker: MockFixture):
        mocker.patch(
            "jikan.commands.project.add_project",
            side_effect=self.mock_project_add,
        )

        result = runner.invoke(
            app,
            [
                "project",
                "add",
                "--name",
                "\nNew Mock Project\n",
                "--description",
                "\nThis is a test project\n",
            ],
        )
        assert result.exit_code == 0
        assert "Success" in result.output
        assert "New Mock Project" in result.output
        assert "This is a test project" in result.output

    def test_short_options(self, mocker: MockFixture):
        mocker.patch(
            "jikan.commands.project.add_project",
            side_effect=self.mock_project_add,
        )

        result = runner.invoke(
            app,
            [
                "project",
                "add",
                "-n",
                "\nNew Mock Project\n",
                "-d",
                "\nThis is a test project\n",
            ],
        )
        assert result.exit_code == 0
        assert "Success" in result.output
        assert "New Mock Project" in result.output
        assert "This is a test project" in result.output

    def test_short_options_success(self, mocker: MockFixture):
        mocker.patch(
            "jikan.commands.project.add_project",
            side_effect=self.mock_project_add,
        )
        result = runner.invoke(
            app,
            ["project", "add", "--name", '"New Mock Project"', "-d", '"This is a test project"'],
        )
        assert result.exit_code == 0
        assert "Success" in result.output
        assert "New Mock Project" in result.output
        assert "This is a test project" in result.output

    def test_no_description_success(self, mocker: MockFixture):
        mocker.patch(
            "jikan.commands.project.add_project",
            side_effect=self.mock_project_add,
        )
        result = runner.invoke(app, ["project", "add", "--name", '"New Mock Project"'])
        assert result.exit_code == 0
        assert "Success" in result.output
        assert "New Mock Project" in result.output

    def test_without_options_validation(self):
        result = runner.invoke(app, ["project", "add", "-d", "'This is a test project'"])
        assert result.exit_code == 2


class TestProjectDelete:
    def test_success(self, mocker: MockFixture):
        project = Project(id=1, name="Test", description="This is a test project")
        mocker.patch("jikan.commands.project.get_project", return_value=project)
        mocker.patch("jikan.commands.project.typer.confirm", return_value=True)
        mocker.patch("jikan.commands.project.delete_project", return_value=None)
        result = runner.invoke(app, ["project", "delete", "1"])
        assert result.exit_code == 0
        assert str(project) in result.output
        assert "Success" in result.output

    def test_without_id_validation(self):
        result = runner.invoke(app, ["project", "delete"])
        assert result.exit_code == 2

    def test_project_not_found_validation(self, mocker: MockFixture):
        mocker.patch(
            "jikan.commands.project.get_project",
            side_effect=ProjectNotFoundError(),
        )
        result = runner.invoke(app, ["project", "delete", "1"])
        assert result.exit_code == 1
        assert "Project not found" in result.output

    def test_confirm_cancel_validation(self, mocker: MockFixture):
        mocker.patch(
            "jikan.commands.project.get_project",
            return_value=Project(id=1, name="Test", description="This is a test project"),
        )
        mocker.patch("jikan.commands.project.typer.confirm", side_effect=Abort)
        result = runner.invoke(app, ["project", "delete", "1"])

        assert result.exit_code == 1


class TestProjectEdit:
    def test_success(self, mocker: MockFixture):
        mocker.patch(
            "jikan.commands.project.get_project",
            return_value=Project(name="Test", description="This is a test project"),
        )
        mocker.patch(
            "jikan.commands.project.edit_project",
            return_value=Project(name="Test", description="This is a test project"),
        )
        result = runner.invoke(
            app,
            [
                "project",
                "edit",
                "1",
                "--name",
                "Test",
                "--description",
                "This is a test project",
            ],
        )

        assert result.exit_code == 0
        assert "Success" in result.output

    def test_only_name_success(self, mocker: MockFixture):
        mocker.patch(
            "jikan.commands.project.get_project",
            return_value=Project(name="Test", description="This is a test project"),
        )
        mocker.patch(
            "jikan.commands.project.edit_project",
            return_value=Project(name="Test", description="This is a test project"),
        )
        result = runner.invoke(app, ["project", "edit", "1", "--name", "Test"])
        assert result.exit_code == 0
        assert "Success" in result.output

    def test_without_options_validation(self):
        result = runner.invoke(app, ["project", "edit", "1"])
        assert result.exit_code == 1

    def test_project_not_found_validation(self, mocker: MockFixture):
        mocker.patch(
            "jikan.commands.project.get_project",
            side_effect=ProjectNotFoundError(),
        )
        result = runner.invoke(app, ["project", "edit", "1", "--name", "Test"])
        assert result.exit_code == 1
        assert "Project not found" in result.output

    def test_options_empty_validation(self):
        result = runner.invoke(app, ["project", "edit", "1", "--name", "", "--description", ""])
        assert result.exit_code == 1
        assert "You must specify either name or description" in result.output


class TestProjectArchive:
    def test_success(self, mocker: MockFixture):
        mocker.patch(
            "jikan.commands.project.get_project",
            return_value=Project(name="Test", description="This is a test project"),
        )
        mocker.patch(
            "jikan.commands.project.set_project_archived",
            return_value=None,
        )
        result = runner.invoke(app, ["project", "archive", "1"])

        assert result.exit_code == 0

    def test_already_archived_success(self, mocker: MockFixture):
        mocker.patch(
            "jikan.commands.project.get_project",
            return_value=Project(name="Test", description="This is a test project", archived=True),
        )
        mocker.patch(
            "jikan.commands.project.set_project_archived",
            return_value=None,
        )
        result = runner.invoke(app, ["project", "archive", "1"])

        assert result.exit_code == 0

    def test_without_id_validation(self):
        result = runner.invoke(app, ["project", "archive"])

        assert result.exit_code == 2


class TestProjectUnarchive:
    def test_success(self, mocker: MockFixture):
        mocker.patch(
            "jikan.commands.project.get_project",
            return_value=Project(name="Test", description="This is a test project"),
        )
        mocker.patch(
            "jikan.commands.project.set_project_archived",
            return_value=None,
        )
        result = runner.invoke(app, ["project", "unarchive", "1"])

        assert result.exit_code == 0

    def test_already_archived_success(self, mocker: MockFixture):
        mocker.patch(
            "jikan.commands.project.get_project",
            return_value=Project(name="Test", description="This is a test project", archived=False),
        )
        mocker.patch(
            "jikan.commands.project.set_project_archived",
            return_value=None,
        )
        result = runner.invoke(app, ["project", "unarchive", "1"])

        assert result.exit_code == 0

    def test_without_id_validation(self):
        result = runner.invoke(app, ["project", "unarchive"])

        assert result.exit_code == 2
