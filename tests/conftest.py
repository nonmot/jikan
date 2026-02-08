from collections.abc import Generator
from contextlib import contextmanager

import pytest
from pytest_mock import MockerFixture
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

from jikan.db import reset_session_factory, session_context, set_session_context_factory
from jikan.models import Entry, Project, Tag


@pytest.fixture()
def use_test_engine(mocker: MockerFixture) -> Generator[None, None, None]:
    test_engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    SQLModel.metadata.create_all(test_engine)

    @contextmanager
    def _test_session_context():
        with Session(test_engine) as session:
            yield session

    set_session_context_factory(_test_session_context)
    try:
        yield
    finally:
        reset_session_factory()
        SQLModel.metadata.drop_all(test_engine)


@pytest.fixture()
def seed_projects(use_test_engine: None) -> None:
    projects = [
        Project(id=1, name="active-1", description="a1", archived=False),
        Project(id=2, name="active-2", description="a2", archived=False),
        Project(id=3, name="archived-1", description="x1", archived=True),
    ]

    with session_context() as session:
        session.add_all(projects)
        session.commit()


@pytest.fixture()
def seed_tags(use_test_engine: None) -> None:
    tags = [
        Tag(id=1, name="tag-1"),
        Tag(id=2, name="tag-2"),
    ]

    with session_context() as session:
        session.add_all(tags)
        session.commit()


@pytest.fixture()
def seed_active_entry(use_test_engine: None) -> None:
    project = Project(id=1, name="active-1", description="a1", archived=False)

    entry = Entry(id=1, project_id=project.id, title="Entry 1", description="Entry 1")

    with session_context() as session:
        session.add(project)
        session.add(entry)
        session.commit()


@pytest.fixture()
def seed_entries(use_test_engine: None) -> None:
    project = Project(id=1, name="project-1")
    tags = [
        Tag(id=1, name="tag-1"),
        Tag(id=2, name="tag-2"),
    ]
    entries = [
        Entry(id=1, project_id=project.id, title="entry-1", description="entry 1", tags=[tags[0]]),
        Entry(
            id=2,
            project_id=project.id,
            title="entry-2",
            description="entry 2",
        ),
    ]

    with session_context() as session:
        session.add(project)
        session.add_all(tags)
        session.add_all(entries)
        session.commit()
