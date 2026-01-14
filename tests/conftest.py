from collections.abc import Generator

import pytest
from pytest_mock import MockerFixture
from sqlalchemy.engine import Engine
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

import jikan.core.project as project_core
from jikan.models import Project


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
    mocker.patch.object(project_core, "engine", test_engine)


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
