from collections.abc import Generator
from datetime import datetime

import pytest
from pytest_mock import MockerFixture
from sqlalchemy.engine import Engine
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

import jikan.core.entry as entry_core
import jikan.core.project as project_core
import jikan.core.tag as tag_core
from jikan.models import Entry, Project, Tag


@pytest.fixture()
def test_engine() -> Generator[Engine, None, None]:
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    SQLModel.metadata.create_all(engine)
    yield engine
    SQLModel.metadata.drop_all(engine)


@pytest.fixture()
def use_test_engine(mocker: MockerFixture, test_engine: Engine) -> None:
    core_modules = (project_core, tag_core, entry_core)
    for module in core_modules:
        mocker.patch.object(module, "engine", test_engine)


@pytest.fixture()
def seed_projects(use_test_engine: None) -> None:
    projects = [
        Project(id=1, name="active-1", description="a1", archived=False),
        Project(id=2, name="active-2", description="a2", archived=False),
        Project(id=3, name="archived-1", description="x1", archived=True),
    ]

    with Session(project_core.engine) as session:
        session.add_all(projects)
        session.commit()


@pytest.fixture()
def seed_tags(use_test_engine: None) -> None:
    tags = [
        Tag(id=1, name="tag-1"),
        Tag(id=2, name="tag-2"),
    ]

    with Session(tag_core.engine) as session:
        session.add_all(tags)
        session.commit()


@pytest.fixture()
def seed_active_entry(use_test_engine: None) -> None:
    project = Project(id=1, name="active-1", description="a1", archived=False)

    entry = Entry(
        id=1, project_id=project.id, title="Entry 1", description="Entry 1", start_at=datetime.now()
    )

    with Session(entry_core.engine) as session:
        session.add(project)
        session.add(entry)
        session.commit()


@pytest.fixture()
def seed_entries(use_test_engine: None) -> None:
    project = Project(id=1, name="project-1")
    entries = [
        Entry(
            id=1,
            project_id=project.id,
            title="entry-1",
            description="entry 1",
            start_at=datetime.now(),
        ),
        Entry(
            id=2,
            project_id=project.id,
            title="entry-2",
            description="entry 2",
            start_at=datetime.now(),
        ),
    ]

    with Session(tag_core.engine) as session:
        session.add(project)
        session.add_all(entries)
        session.commit()
