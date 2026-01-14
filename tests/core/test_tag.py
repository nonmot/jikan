import pytest

from jikan.core.tag import Tag, TagNotFoundError, add_tag, delete_tag, edit_tag, get_tag, list_tag


class TestTagList:
    def test_success(self, seed_tags: None):
        tags = list_tag()
        names = {t.name for t in tags}
        assert len(tags) == 2
        assert names == {"tag-1", "tag-2"}

    def test_empty_tag(self, use_test_engine: None):
        tags = list_tag()
        assert tags == []


class TestTagGet:
    def test_success(self, seed_tags: None):
        tag = get_tag(1)
        assert tag is not None
        assert tag.id == 1
        assert tag.name == "tag-1"

    def test_tag_not_found(self, seed_tags: None):
        with pytest.raises(TagNotFoundError):
            get_tag(id=1000)


class TestTagAdd:
    def test_add_one_tag(self, seed_tags: None):
        tags_before = list_tag()
        add_tag(name="tag-3")
        tags_after = list_tag()
        assert len(tags_before) + 1 == len(tags_after)

    def test_added_tag_has_id(self, use_test_engine: None):
        tag = add_tag(name="Test tag")
        assert tag.id is not None

    def test_added_tag_property(self, use_test_engine: None):
        tag = add_tag(name="Test Tag")
        added_tag = get_tag(tag.id)

        assert added_tag.name == "Test Tag"

    def test_name_should_not_be_empty(self, use_test_engine: None):
        with pytest.raises(ValueError):
            add_tag(name="")


class TestTagEdit:
    def test_success(self, seed_tags: None):
        tag_to_be_edited = get_tag(1)
        edit_tag(tag_to_be_edited, "edited-tag-1")
        tag = get_tag(1)
        assert tag.name == "edited-tag-1"

    def test_returned_tag_updated(self, seed_tags: None):
        tag_to_be_edited = get_tag(1)
        tag = edit_tag(tag_to_be_edited, "edited-tag-1")
        assert tag.name == "edited-tag-1"

    def test_tag_not_found(self, seed_tags: None):
        not_exist_tag = Tag(id=1000, name="hoge")
        with pytest.raises(TagNotFoundError):
            edit_tag(not_exist_tag, "huga")


class TestTagDelete:
    def test_success(self, seed_tags: None):
        tags_before = list_tag()
        tag_to_be_deleted = get_tag(2)
        delete_tag(tag_to_be_deleted)
        tags_after = list_tag()
        assert len(tags_before) - 1 == len(tags_after)

        names = {t.name for t in tags_after}
        assert names == {"tag-1"}

    def test_tag_not_found(self, seed_tags: None):
        not_exist_tag = Tag(id=1000, name="hoge")
        with pytest.raises(TagNotFoundError):
            delete_tag(not_exist_tag)
