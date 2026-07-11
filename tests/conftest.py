import os
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine
from sqlalchemy.pool import StaticPool
from sqlmodel import create_engine

from dashski import db

# Must be set before TestClient enters the app lifespan, which starts the scheduler.
os.environ["DASHSKI_SCHEDULER"] = "0"


@pytest.fixture
def engine() -> Iterator[Engine]:
    """In-memory SQLite engine, swapped in for the app's engine. Never touches data/."""
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    db.init_db(engine)
    db.set_engine(engine)
    yield engine
    db.set_engine(None)


@pytest.fixture
def client(engine: Engine) -> Iterator[TestClient]:
    from dashski.main import app

    with TestClient(app) as client:
        yield client
