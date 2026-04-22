"""Shared pytest fixtures.

Every test gets its own SQLite-in-memory database and a `get_session`
override bound to that DB. This keeps tests fast and hermetic; Postgres
parity is validated by the Alembic migration in CI.
"""

from __future__ import annotations

from collections.abc import Generator

import pytest
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.session import get_session as real_get_session
from app.db import models  # noqa: F401  registers tables with Base.metadata
from app.main import app


@pytest.fixture
def db_engine() -> Generator[Engine, None, None]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    Base.metadata.create_all(engine)
    try:
        yield engine
    finally:
        Base.metadata.drop_all(engine)
        engine.dispose()


@pytest.fixture
def db_session_factory(db_engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=db_engine, autoflush=False, autocommit=False, future=True)


@pytest.fixture
def db_session(db_session_factory: sessionmaker[Session]) -> Generator[Session, None, None]:
    session = db_session_factory()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def override_db(
    db_session_factory: sessionmaker[Session],
    monkeypatch: pytest.MonkeyPatch,
) -> Generator[None, None, None]:
    """Override the DB dependency *and* the module-level get_session.

    The FastAPI override handles endpoint tests; the module-level monkey-patch
    handles direct callers like Mai Filer's document tools, which use
    `next(get_session())` outside the request lifecycle.
    """

    def _get_session() -> Generator[Session, None, None]:
        session = db_session_factory()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[real_get_session] = _get_session
    monkeypatch.setattr("app.db.session.get_session", _get_session)
    # Patch the re-bound name inside modules that imported get_session directly.
    monkeypatch.setattr(
        "app.agents.mai_filer.tools.get_session", _get_session, raising=False
    )
    try:
        yield
    finally:
        app.dependency_overrides.pop(real_get_session, None)
