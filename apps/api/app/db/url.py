"""Database URL helpers.

Railway's Postgres plugin (and most managed Postgres providers) hand you
a connection string like `postgresql://user:pass@host/db` or the older
`postgres://...` — both default to the psycopg2 driver when SQLAlchemy
parses them. Mai Filer ships with psycopg (v3) per pyproject.toml, so
we rewrite the scheme to `postgresql+psycopg://` before creating any
engine.

Keep this logic in one module so `app/db/session.py` and `alembic/env.py`
use the same conversion.
"""

from __future__ import annotations


def normalize_database_url(url: str) -> str:
    """Return `url` with a psycopg3-compatible scheme if it targets Postgres.

    - `postgres://...`            → `postgresql+psycopg://...`
    - `postgresql://...`          → `postgresql+psycopg://...`
    - `postgresql+psycopg://...`  → unchanged (already correct)
    - `postgresql+psycopg2://...` → unchanged (respect explicit opt-in)
    - `sqlite://...` / anything else → unchanged.
    """
    if not url:
        return url
    if url.startswith("postgresql+"):
        return url  # already carries an explicit driver choice
    if url.startswith("postgres://"):
        return "postgresql+psycopg://" + url[len("postgres://") :]
    if url.startswith("postgresql://"):
        return "postgresql+psycopg://" + url[len("postgresql://") :]
    return url


__all__ = ["normalize_database_url"]
