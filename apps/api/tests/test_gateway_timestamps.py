"""NRS timestamp tests (P6.2)."""

from __future__ import annotations

import re
from datetime import datetime, timezone

import pytest

from app.gateway.timestamps import (
    REPLAY_WINDOW_SECONDS,
    TimestampError,
    iso_20022_now,
    parse_iso_20022,
    within_replay_window,
)

ISO_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$")


def test_iso_20022_now_shape() -> None:
    stamp = iso_20022_now()
    assert ISO_RE.match(stamp), f"bad format: {stamp}"


def test_iso_20022_now_is_injectable() -> None:
    fixed = datetime(2026, 4, 22, 9, 15, 30, 123456, tzinfo=timezone.utc)
    assert iso_20022_now(fixed) == "2026-04-22T09:15:30.123Z"


def test_parse_iso_20022_roundtrip() -> None:
    fixed = datetime(2026, 4, 22, 9, 15, 30, 123000, tzinfo=timezone.utc)
    s = iso_20022_now(fixed)
    parsed = parse_iso_20022(s)
    assert parsed == fixed


def test_parse_iso_20022_rejects_garbage() -> None:
    with pytest.raises(TimestampError):
        parse_iso_20022("not a timestamp")
    with pytest.raises(TimestampError):
        parse_iso_20022("")


def test_within_replay_window_passes_inside_window() -> None:
    now = datetime(2026, 4, 22, 10, 0, 0, tzinfo=timezone.utc)
    inside = "2026-04-22T09:56:00.000Z"  # 4 minutes earlier
    assert within_replay_window(inside, now=now) is True


def test_within_replay_window_rejects_outside() -> None:
    now = datetime(2026, 4, 22, 10, 0, 0, tzinfo=timezone.utc)
    outside = "2026-04-22T09:00:00.000Z"  # 1 hour earlier
    assert within_replay_window(outside, now=now) is False


def test_default_window_is_five_minutes() -> None:
    assert REPLAY_WINDOW_SECONDS == 300
