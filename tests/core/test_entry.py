import pytest

from jikan.core.entry import (
    EntryAlreadyRunningError,
    EntryNotRunningError,
    get_running_entry,
    list_time_entry,
    start_time_entry,
    stop_time_entry,
)


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
