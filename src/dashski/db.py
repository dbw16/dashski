"""Engine and session management. DASHSKI_DB_URL overrides the default file path."""

import os
from collections.abc import Iterator
from pathlib import Path

from sqlalchemy import Engine
from sqlmodel import Session, SQLModel, create_engine

DEFAULT_DB_PATH = Path("data") / "dashski.db"

_engine: Engine | None = None


def _database_url() -> str:
    url = os.environ.get("DASHSKI_DB_URL")
    if url:
        return url
    DEFAULT_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    return f"sqlite:///{DEFAULT_DB_PATH}"


def get_engine() -> Engine:
    global _engine
    if _engine is None:
        _engine = create_engine(_database_url(), connect_args={"check_same_thread": False})
    return _engine


def set_engine(engine: Engine | None) -> None:
    """Point the app at a different engine (used by tests)."""
    global _engine
    _engine = engine


def init_db(engine: Engine) -> None:
    SQLModel.metadata.create_all(engine)


def get_session() -> Iterator[Session]:
    with Session(get_engine()) as session:
        yield session
