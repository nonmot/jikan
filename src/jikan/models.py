from datetime import datetime

from sqlmodel import Field, Relationship, SQLModel

from jikan.lib.datetime import utc_now


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
