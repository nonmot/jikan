"""Read classification candidates on every shell completion request."""

import sqlite3
from contextlib import closing
from pathlib import Path

from sqlmodel import select

from jikan.db import session_context
from jikan.models import Project, Tag


def _names(model: type[Project] | type[Tag], incomplete: str) -> list[str]:
    try:
        with session_context() as session:
            bind = session.get_bind()
            database = bind.url.database
            if bind.dialect.name == "sqlite" and database not in (None, "", ":memory:"):
                # mode=ro avoids creating a missing DB, including deletion races.
                uri = Path(database).resolve().as_uri() + "?mode=ro"
                with closing(sqlite3.connect(uri, uri=True, timeout=0.1)) as connection:
                    names = [
                        row[0]
                        for row in connection.execute(
                            f'SELECT name FROM "{model.__tablename__}" ORDER BY name'
                        )
                    ]
            else:
                names = session.exec(select(model.name).order_by(model.name)).all()
            return [name for name in names if name.startswith(incomplete)]
    except Exception:
        # Completion must remain silent and safe before init or on a broken DB.
        return []


def complete_projects(incomplete: str) -> list[str]:
    return _names(Project, incomplete)


def complete_tags(incomplete: str) -> list[str]:
    return _names(Tag, incomplete)
