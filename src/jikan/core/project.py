from collections.abc import Sequence

from sqlmodel import Session, select

from jikan.models import Project, engine


class ProjectNotFoundError(Exception):
    pass


def list_project() -> Sequence[Project]:
    with Session(engine) as session:
        statement = select(Project).where(Project.archived == False)  # noqa E712
        projects = session.exec(statement).all()
        return projects


def add_project(name: str, description: str) -> Project:
    if not name:
        raise ValueError("name should not be empty")
    new_project = Project(name=name, description=description)
    with Session(engine) as session:
        session.add(new_project)
        session.commit()
        session.refresh(new_project)
    return new_project


def get_project(id: int) -> Project:
    with Session(engine) as session:
        statement = select(Project).where(Project.id == id)
        project = session.exec(statement).one_or_none()
        if project is None:
            raise ProjectNotFoundError
        return project


def delete_project(project: Project) -> None:
    with Session(engine) as session:
        db_project = session.get(Project, project.id)
        if db_project is None:
            raise ProjectNotFoundError
        session.delete(db_project)
        session.commit()


def edit_project(project: Project, name: str | None, description: str | None) -> Project:
    with Session(engine) as session:
        db_project = session.get(Project, project.id)
        if db_project is None:
            raise ProjectNotFoundError
        if name is not None:
            db_project.name = name
        if description is not None:
            db_project.description = description
        session.add(db_project)
        session.commit()
        session.refresh(db_project)

    return db_project


def set_project_archived(project: Project, is_archived: bool) -> Project:
    with Session(engine) as session:
        db_project = session.get(Project, project.id)
        if db_project is None:
            raise ProjectNotFoundError
        db_project.archived = is_archived
        session.add(db_project)
        session.commit()
        session.refresh(db_project)
        return db_project
