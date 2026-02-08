from collections.abc import Callable, Iterator
from contextlib import AbstractContextManager, contextmanager
from datetime import timedelta
from pathlib import Path

from sqlmodel import Session, SQLModel, create_engine, inspect

from jikan.lib.datetime import utc_now
from jikan.models import Entry, Project, Tag

SQLITE_FILE_NAME = "database.db"
APP_DIR = Path.home() / ".jikan"
APP_DIR.mkdir(parents=True, exist_ok=True)
SQLITE_PATH = APP_DIR / SQLITE_FILE_NAME
SQLITE_URL = f"sqlite:///{SQLITE_PATH}"

engine = create_engine(SQLITE_URL)

SessionContextFactory = Callable[[], AbstractContextManager[Session]]


@contextmanager
def _default_session_context() -> Iterator[Session]:
    with Session(engine) as session:
        yield session


_session_context_factory: SessionContextFactory = _default_session_context


def session_context() -> AbstractContextManager[Session]:
    return _session_context_factory()


def set_session_context_factory(factory: SessionContextFactory) -> None:
    global _session_context_factory
    _session_context_factory = factory


def reset_session_factory() -> None:
    global _session_context_factory
    _session_context_factory = _default_session_context


def create_db_and_tables() -> None:
    inspector = inspect(engine)
    if inspector.has_table("project"):
        print("Table project exist.")
        return
    else:
        SQLModel.metadata.create_all(engine)

        project = Project(
            name="Learn about jikan",
            description="Learn about jikan to manage your time effectively!",
            archived=False,
        )
        with Session(engine) as session:
            session.add(project)
            session.commit()
            session.refresh(project)

        tag1 = Tag(name="Read docs")
        tag2 = Tag(name="Use jikan")
        with Session(engine) as session:
            session.add(tag1)
            session.add(tag2)
            session.commit()
            session.refresh(tag1)
            session.refresh(tag2)

        assert project.id is not None
        entry = Entry(
            title="Install jikan and give it a try",
            description="Dive in jikan to explore what it's all about!",
            project=project,
            tags=[tag1, tag2],
        )
        inbox_entry = Entry(
            title="Inbox",
            tags=[tag1, tag2],
        )
        entry.end_at = utc_now() + timedelta(seconds=10)
        inbox_entry.end_at = utc_now() + timedelta(seconds=10)
        with Session(engine) as session:
            session.add(entry)
            session.add(inbox_entry)
            session.commit()
