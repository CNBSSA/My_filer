"""SQLAlchemy engine and session factory.

v1 uses sync SQLAlchemy; FastAPI endpoints remain async but call the DB via
a thread-pooled `Session`. Async SA is a later optimization.

Engine creation is lazy so tests (which override `get_session` via
`app.dependency_overrides`) don't require the Postgres driver to be
installed. Set `DATABASE_URL=sqlite:///./mai_filer.db` for a file-backed
dev DB, or `sqlite://` for in-memory.
"""

from __future__ import annotations

from collections.abc import Generator
from functools import lru_cache

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings


def _make_engine(database_url: str) -> Engine:
    connect_args: dict = {}
    if database_url.startswith("sqlite"):
        connect_args["check_same_thread"] = False
    return create_engine(database_url, future=True, connect_args=connect_args)


@lru_cache(maxsize=1)
def _engine() -> Engine:
    return _make_engine(get_settings().database_url)


@lru_cache(maxsize=1)
def _session_factory() -> sessionmaker[Session]:
    return sessionmaker(bind=_engine(), autoflush=False, autocommit=False, future=True)


def get_session() -> Generator[Session, None, None]:
    """FastAPI dependency yielding a DB session and guaranteeing close."""
    session = _session_factory()()
    try:
        yield session
    finally:
        session.close()
