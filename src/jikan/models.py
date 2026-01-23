from datetime import datetime
from pathlib import Path

from sqlmodel import Field, Session, SQLModel, create_engine, inspect

SQLITE_FILE_NAME = "database.db"
APP_DIR = Path.home() / ".jikan"
APP_DIR.mkdir(parents=True, exist_ok=True)
SQLITE_PATH = APP_DIR / SQLITE_FILE_NAME
SQLITE_URL = f"sqlite:///{SQLITE_PATH}"

engine = create_engine(SQLITE_URL)


class Project(SQLModel, table=True):
    id: int = Field(default=None, primary_key=True)
    name: str
    description: str | None = None
    archived: bool = Field(default=False)

    def __str__(self) -> str:
        return f"Project(id={self.id}, name={self.name})"


class Entry(SQLModel, table=True):
    id: int = Field(default=None, primary_key=True)
    project_id: int = Field(foreign_key="project.id")
    title: str
    description: str
    start_at: datetime
    end_at: datetime | None = None
    created_at: datetime = Field(default_factory=datetime.now, nullable=True)
    updated_at: datetime = Field(default_factory=datetime.now)

    def __str__(self) -> str:
        return f"Entry(id={self.id}, title={self.title})"


class Tag(SQLModel, table=True):
    id: int = Field(default=None, primary_key=True)
    name: str

    def __str__(self) -> str:
        return f"Tag(id={self.id}, name={self.name})"


def create_db_and_tables() -> None:
    inspector = inspect(engine)
    if inspector.has_table("project"):
        print("Table project exist.")
        return
    else:
        SQLModel.metadata.create_all(engine)

        project1 = Project(name="Test1", description="This is a test project", archived=False)
        project2 = Project(name="Test2", archived=False)
        project3 = Project(name="Test3", archived=False)

        tag1 = Tag(name="Tag1")
        tag2 = Tag(name="Tag2")
        tag3 = Tag(name="Tag3")

        with Session(engine) as session:
            session.add(project1)
            session.add(project2)
            session.add(project3)

            session.add(tag1)
            session.add(tag2)
            session.add(tag3)

            session.commit()
