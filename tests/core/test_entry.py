from datetime import datetime, timedelta

import pytest
from pytest_mock import MockFixture

from jikan.core.entry import (
    EntryAlreadyRunningError,
    EntryNotFoundError,
    EntryNotRunningError,
    delete_entry,
    edit_entry,
    get_entry,
    get_running_entry,
    list_time_entry,
    start_time_entry,
    stop_time_entry,
)
from jikan.core.project import ProjectNotFoundError
from jikan.lib.datetime import utc_now
from jikan.models import Entry, Project


class TestGetEntry:
    def test_get_entry(self, seed_entries: None):
        entry = get_entry(1)
        assert entry is not None

    def test_entry_not_found(self, seed_entries: None):
        with pytest.raises(EntryNotFoundError):
            get_entry(1000)


class TestEditEntry:
    def test_success(self, seed_entries: None):
        now = datetime.now()  # TO BE FIXED
        entry = get_entry(1)
        edit_entry(entry, "Edited", "Edited", now, now, 1)
        entry = get_entry(1)

        assert entry.title == "Edited"
        assert entry.description == "Edited"
        assert entry.start_at == now
        assert entry.end_at == now
        assert entry.project_id == 1

    def test_options_are_none(self, seed_entries: None):
        entry_before = get_entry(1)
        edit_entry(entry_before, None, None)
        entry_after = get_entry(1)

        assert entry_after.title is not None
        assert entry_after.description is not None
        assert entry_before.title == entry_after.title
        assert entry_before.description == entry_after.description

    def test_description_is_empty(self, seed_entries: None):
        entry_before = get_entry(1)
        edit_entry(entry_before, "Edited", "")
        entry_after = get_entry(1)

        assert entry_after.title == "Edited"
        assert entry_after.description == ""

    def test_entry_not_found(self, seed_entries: None):
        not_exist_entry = Entry(
            id=1000, project_id=1000, title="entry", description="entry", start_at=datetime.now()
        )
        with pytest.raises(EntryNotFoundError):
            edit_entry(not_exist_entry, "edited", "edited")

    def test_associated_project_not_found(self, seed_entries: None):
        project = Project(id=1000, name="Not exist")
        entry = get_entry(1)
        with pytest.raises(ProjectNotFoundError):
            edit_entry(entry, "Edited", "Edited", project_id=project.id)

    def test_end_is_later_than_start(self, seed_entries: None):
        entry = get_entry(1)
        now = datetime.now()
        future = now + timedelta(seconds=10)
        with pytest.raises(ValueError):
            edit_entry(entry, "Edited", "Edited", future, now)


class TestEntryDelete:
    def test_success(self, seed_entries: None):
        entries_before = list_time_entry()
        entry = get_entry(1)
        delete_entry(entry)
        entries_after = list_time_entry()

        assert len(entries_before) - 1 == len(entries_after)

    def test_entry_not_found(self, seed_entries: None):
        not_exist_entry = Entry(
            id=1000,
            project_id=1,
            title="not-exist-entry",
            description="not exist entry",
            start_at=datetime.now(),
        )
        with pytest.raises(EntryNotFoundError):
            delete_entry(not_exist_entry)


class TestStartTimeEntry:
    def test_success(self, use_test_engine: None):
        entries_before = list_time_entry()

        start_time_entry(1, "Test", "Test")
        entries_after = list_time_entry()

        assert len(entries_before) + 1 == len(entries_after)
        assert entries_after[-1].title == "Test"
        assert entries_after[-1].description == "Test"
        assert entries_after[-1].end_at is None

    def test_empty_title_success(self, use_test_engine: None):
        entries_before = list_time_entry()

        start_time_entry(1, "", "")
        entries_after = list_time_entry()

        assert len(entries_before) + 1 == len(entries_after)
        assert entries_after[-1].title == ""
        assert entries_after[-1].description == ""
        assert entries_after[-1].end_at is None

    def test_returned_value_has_correct_property(self, use_test_engine: None):
        entry = start_time_entry(1, "Test", "Test")

        assert entry.title == "Test"
        assert entry.description == "Test"
        assert entry.end_at is None

    def test_entry_already_running(self, seed_active_entry: None):
        with pytest.raises(EntryAlreadyRunningError):
            start_time_entry(1, "Test", "Test")


class TestStopTimeEntry:
    def test_success(self, seed_active_entry: None):
        stop_time_entry()
        entries = list_time_entry()

        assert entries[-1].end_at is not None

    def test_no_entry_running(self, use_test_engine: None):
        with pytest.raises(EntryNotRunningError):
            stop_time_entry()

    def test_returned_value_has_correct_property(self, seed_active_entry: None):
        entry = stop_time_entry()
        assert entry.end_at is not None

    def test_time_should_be_later_than_start(self, seed_active_entry: None, mocker: MockFixture):
        mocker.patch("jikan.core.entry.utc_now", return_value=utc_now() - timedelta(days=1))
        with pytest.raises(RuntimeError):
            stop_time_entry()


class TestGetRunningEntry:
    def test_success(self, seed_active_entry: None):
        entries = get_running_entry()
        assert entries != []

    def test_no_running_entry(self, use_test_engine: None):
        entries = get_running_entry()
        assert entries == []


class TestListTimeEntry:
    def test_success(self, use_test_engine: None):
        start_time_entry(1, "Test1", "Test1")
        stop_time_entry()
        start_time_entry(1, "Test2", "Test2")

        entries = list_time_entry()

        assert len(entries) == 2

    def test_no_entry(self, use_test_engine: None):
        entries = list_time_entry()
        assert entries == []
