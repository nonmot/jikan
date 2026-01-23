from datetime import datetime, timedelta
from pathlib import Path

from sqlmodel import Field, Relationship, Session, SQLModel, create_engine, inspect

from jikan.lib.datetime import utc_now

SQLITE_FILE_NAME = "database.db"
APP_DIR = Path.home() / ".jikan"
APP_DIR.mkdir(parents=True, exist_ok=True)
SQLITE_PATH = APP_DIR / SQLITE_FILE_NAME
SQLITE_URL = f"sqlite:///{SQLITE_PATH}"

engine = create_engine(SQLITE_URL)


class EntryTagLink(SQLModel, table=True):
    entry_id: int = Field(foreign_key="entry.id", ondelete="CASCADE", primary_key=True)
    tag_id: int = Field(foreign_key="tag.id", ondelete="CASCADE", primary_key=True)


class Project(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(index=True, unique=True)
    description: str = Field(default="")
    archived: bool = Field(default=False)

    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)

    entries: list["Entry"] = Relationship(back_populates="project")

    def __str__(self) -> str:
        return f"Project(id={self.id}, name={self.name})"


class Tag(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(index=True, unique=True)
    created_at: datetime = Field(default_factory=utc_now)

    entries: list["Entry"] = Relationship(back_populates="tags", link_model=EntryTagLink)

    def __str__(self) -> str:
        return f"Tag(id={self.id}, name={self.name})"


class Entry(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    title: str | None = Field(default=None)
    description: str | None = Field(default=None)
    start_at: datetime = Field(default_factory=utc_now)
    end_at: datetime | None = Field(default=None, index=True)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)

    project_id: int | None = Field(default=None, foreign_key="project.id")
    project: Project | None = Relationship(back_populates="entries")
    tags: list[Tag] = Relationship(back_populates="entries", link_model=EntryTagLink)

    def __str__(self) -> str:
        return f"Entry(id={self.id}, title={self.title})"


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
