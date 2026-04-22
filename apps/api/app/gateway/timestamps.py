"""Timestamp helpers for the NRS handshake (P6.2).

NRS accepts ISO-20022 — a UTC instant with milliseconds and a `Z` suffix,
e.g. `2026-04-22T09:15:30.123Z`.

We also expose a `within_replay_window` guard for validating inbound
timestamps if / when NRS starts calling our webhooks. The default window
is 5 minutes, which is a common value for financial messaging.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

REPLAY_WINDOW_SECONDS = 300  # 5 minutes


class TimestampError(ValueError):
    """Raised for malformed or out-of-window timestamps."""


def iso_20022_now(now: datetime | None = None) -> str:
    """Return the current UTC instant as an ISO-20022 string.

    Injectable `now` keeps tests deterministic.
    """
    ts = (now or datetime.now(tz=timezone.utc)).astimezone(timezone.utc)
    return ts.strftime("%Y-%m-%dT%H:%M:%S.") + f"{ts.microsecond // 1000:03d}Z"


def parse_iso_20022(value: str) -> datetime:
    """Parse `YYYY-MM-DDTHH:MM:SS[.sss][Z]` back to a UTC datetime."""
    if not value:
        raise TimestampError("empty timestamp")
    normalized = value.strip()
    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise TimestampError(f"unparseable timestamp: {value!r}") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def within_replay_window(
    value: str,
    *,
    now: datetime | None = None,
    window_seconds: int = REPLAY_WINDOW_SECONDS,
) -> bool:
    """True iff `value` is within `window_seconds` of `now` (default: UTC now)."""
    ts = parse_iso_20022(value)
    current = (now or datetime.now(tz=timezone.utc)).astimezone(timezone.utc)
    delta = abs(current - ts)
    return delta <= timedelta(seconds=window_seconds)


__all__ = [
    "REPLAY_WINDOW_SECONDS",
    "TimestampError",
    "iso_20022_now",
    "parse_iso_20022",
    "within_replay_window",
]
