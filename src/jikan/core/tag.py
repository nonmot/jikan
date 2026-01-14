from collections.abc import Sequence

from sqlmodel import Session, select

from jikan.models import Tag, engine


class TagNotFoundError(Exception):
    pass


def list_tag() -> Sequence[Tag]:
    with Session(engine) as session:
        statement = select(Tag)
        tags = session.exec(statement).all()
        return tags


def get_tag(id: int) -> Tag:
    with Session(engine) as session:
        statement = select(Tag).where(Tag.id == id)
        tag = session.exec(statement).one_or_none()
        if tag is None:
            raise TagNotFoundError
        return tag


def add_tag(name: str) -> Tag:
    if not name:
        raise ValueError("name should not be empty")
    with Session(engine) as session:
        tag = Tag(name=name)
        session.add(tag)
        session.commit()
        session.refresh(tag)
        return tag


def edit_tag(tag: Tag, name: str) -> Tag:
    if not name:
        raise ValueError("name should not be empty")
    with Session(engine) as session:
        db_tag = session.get(Tag, tag.id)
        if db_tag is None:
            raise TagNotFoundError
        db_tag.name = name
        session.add(db_tag)
        session.commit()
        session.refresh(db_tag)
        return db_tag


def delete_tag(tag: Tag) -> None:
    with Session(engine) as session:
        db_tag = session.get(Tag, tag.id)
        if db_tag is None:
            raise TagNotFoundError
        session.delete(db_tag)
        session.commit()
