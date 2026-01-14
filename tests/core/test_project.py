import pytest

from jikan.core.project import (
    ProjectNotFoundError,
    add_project,
    delete_project,
    edit_project,
    get_project,
    list_project,
    set_project_archived,
)
from jikan.models import Project


class TestProjectList:
    def test_only_active_returned(self, seed_projects: None):
        projects = list_project()
        names = {p.name for p in projects}
        assert names == {"active-1", "active-2"}

    def test_empty_project(self, use_test_engine: None):
        projects = list_project()
        assert projects == []

    def test_only_archived_project(self, use_test_engine: None):
        archived_project = add_project(name="Archived", description="")
        set_project_archived(archived_project, True)
        projects = list_project()
        assert projects == []


class TestProjectAdd:
    def test_add_one_project(self, seed_projects: None):
        projects_before = list_project()
        add_project(name="active-2", description="")
        projects_after = list_project()
        assert len(projects_before) + 1 == len(projects_after)

    def test_added_project_has_id(self, use_test_engine: None):
        project = add_project(name="test", description="This is a test")
        assert project.id is not None

    def test_added_project_property(self, use_test_engine: None):
        project = add_project(name="Test Project", description="This is a test project")
        id = project.id
        added_project = get_project(id)

        assert added_project.name == "Test Project"
        assert added_project.description == "This is a test project"

    def test_name_should_not_be_empty(self, use_test_engine: None):
        with pytest.raises(ValueError):
            add_project(name="", description="This is a test project")


class TestProjectGet:
    def test_success(self, seed_projects: None):
        project = get_project(1)
        assert project is not None
        assert project.name == "active-1"

    def test_archived_project_success(self, seed_projects: None):
        archived_project = get_project(3)
        assert archived_project is not None
        assert archived_project.archived

    def test_project_not_found(self, seed_projects: None):
        with pytest.raises(ProjectNotFoundError):
            get_project(id=1000)


class TestProjectDelete:
    def test_success(self, seed_projects: None):
        projects_before = list_project()
        project_to_be_deleted = get_project(2)
        delete_project(project_to_be_deleted)
        projects_after = list_project()
        assert len(projects_before) - 1 == len(projects_after)

        names = {p.name for p in projects_after}
        assert names == {"active-1"}

    def test_project_not_found(self, seed_projects: None):
        not_exist_project = Project(id=1000, name="hoge")
        with pytest.raises(ProjectNotFoundError):
            delete_project(not_exist_project)


class TestProjectEdit:
    def test_success(self, seed_projects: None):
        project_to_be_edited = get_project(1)
        edit_project(project_to_be_edited, "edited-active-1", "edited a1")
        project = get_project(1)
        assert project.name == "edited-active-1"
        assert project.description == "edited a1"

    def test_returned_project_updated(self, seed_projects: None):
        project_to_be_edited = get_project(1)
        project = edit_project(project_to_be_edited, "edited-active-1", "edited a1")
        assert project.name == "edited-active-1"
        assert project.description == "edited a1"

    def test_only_name_update(self, seed_projects: None):
        project_to_be_edited = get_project(1)
        edit_project(project_to_be_edited, None, "edited a1")
        project = get_project(1)
        assert project.name == project_to_be_edited.name
        assert project.description == "edited a1"

    def test_only_description_update(self, seed_projects: None):
        project_to_be_edited = get_project(1)
        edit_project(project_to_be_edited, "edited-active-1", None)
        project = get_project(1)
        assert project.name == "edited-active-1"
        assert project.description == project_to_be_edited.description

    def test_project_not_found(self, seed_projects: None):
        not_exist_project = Project(id=1000, name="hoge")
        with pytest.raises(ProjectNotFoundError):
            edit_project(not_exist_project, "huga", "piyo")


class TestProjectSetArchived:
    def test_success(self, seed_projects: None):
        projects_before = list_project()
        project_to_be_archived = get_project(1)
        assert project_to_be_archived in projects_before
        set_project_archived(project_to_be_archived, True)
        project = get_project(1)
        projects_after = list_project()

        assert project.archived
        assert len(projects_before) - 1 == len(projects_after)
        assert project not in projects_after

    def test_returned_project_updated(self, seed_projects: None):
        projects_before = list_project()
        project_to_be_archived = get_project(1)
        assert project_to_be_archived in projects_before
        archived_project = set_project_archived(project_to_be_archived, True)

        assert archived_project.archived

    def test_unarchived_project_listed(self, seed_projects: None):
        projects_before = list_project()
        project_to_be_unarchived = get_project(3)
        assert project_to_be_unarchived.archived
        set_project_archived(project_to_be_unarchived, False)
        project = get_project(3)
        projects_after = list_project()

        assert len(projects_before) + 1 == len(projects_after)
        assert not project.archived
        assert project in projects_after

    def test_project_not_found(self, seed_projects: None):
        not_exist_project = Project(id=1000, name="hoge")
        with pytest.raises(ProjectNotFoundError):
            set_project_archived(not_exist_project, True)
