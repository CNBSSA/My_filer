"""SQLAlchemy base class. All ORM models inherit from `Base`."""

from __future__ import annotations

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Declarative base for Mai Filer ORM models."""
