"""URL normalizer tests — guards the Railway/Heroku → psycopg3 rewrite."""

from __future__ import annotations

import pytest

from app.db.url import normalize_database_url


@pytest.mark.parametrize(
    "raw, expected",
    [
        # Railway / Heroku legacy scheme
        (
            "postgres://u:p@host:5432/db",
            "postgresql+psycopg://u:p@host:5432/db",
        ),
        # Railway current scheme
        (
            "postgresql://u:p@host:5432/db",
            "postgresql+psycopg://u:p@host:5432/db",
        ),
        # Already-correct URLs pass through untouched
        (
            "postgresql+psycopg://u:p@host:5432/db",
            "postgresql+psycopg://u:p@host:5432/db",
        ),
        # Explicit psycopg2 opt-in is respected
        (
            "postgresql+psycopg2://u:p@host:5432/db",
            "postgresql+psycopg2://u:p@host:5432/db",
        ),
        # SQLite and empty strings untouched
        ("sqlite:///./mai_filer.db", "sqlite:///./mai_filer.db"),
        ("sqlite://", "sqlite://"),
        ("", ""),
    ],
)
def test_normalize_database_url(raw: str, expected: str) -> None:
    assert normalize_database_url(raw) == expected


def test_preserves_query_string_and_ssl_flags() -> None:
    raw = "postgres://u:p@host:5432/db?sslmode=require&application_name=mai"
    assert normalize_database_url(raw) == (
        "postgresql+psycopg://u:p@host:5432/db?sslmode=require&application_name=mai"
    )
