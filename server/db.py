"""SQLAlchemy engine helpers shared by API and service layers."""

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from server.settings import Settings


def create_db_engine(settings: Settings) -> Engine:
    options: dict[str, object] = {"future": True}
    if settings.database_url.startswith("sqlite"):
        options["connect_args"] = {"check_same_thread": False}
    return create_engine(settings.database_url, **options)


def create_session_factory(settings: Settings) -> sessionmaker[Session]:
    return sessionmaker(
        bind=create_db_engine(settings),
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
    )
