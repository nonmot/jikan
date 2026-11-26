from collections.abc import Callable, Iterator
from contextlib import AbstractContextManager, contextmanager
from pathlib import Path

from sqlalchemy import text
from sqlmodel import Session, SQLModel, create_engine

from jikan import models  # noqa: F401 — register tables before create_all

SQLITE_FILE_NAME = "database.db"
APP_DIR = Path.home() / ".jikan"
APP_DIR.mkdir(parents=True, exist_ok=True)
SQLITE_PATH = APP_DIR / SQLITE_FILE_NAME
SQLITE_URL = f"sqlite:///{SQLITE_PATH}"

engine = create_engine(SQLITE_URL, connect_args={"timeout": 30})

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


def reset_session_context_factory() -> None:
    global _session_context_factory
    _session_context_factory = _default_session_context


@contextmanager
def recording_session_context() -> Iterator[Session]:
    """Serialize recording mutations before reading the running state.

    BEGIN IMMEDIATE makes a competing SQLite process wait *before* it reads,
    so start/start and start/switch cannot both observe an empty database.
    Session.close rolls back every uncommitted change on failure.
    """
    with session_context() as session:
        if session.get_bind().dialect.name == "sqlite":
            session.execute(text("BEGIN IMMEDIATE"))
        yield session


def create_db_and_tables() -> None:
    """Initialize an empty database; repeated initialization preserves data."""
    SQLModel.metadata.create_all(engine)
