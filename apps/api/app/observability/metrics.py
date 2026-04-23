"""Process-local counters + histograms with a /metrics endpoint.

Zero-dep: renders in the Prometheus text-exposition format. When the
owner provisions a proper scraper we either keep this shape or drop
`prometheus_client` in; callers don't change.

Thread-safety: a single `Lock` guards mutations. CPython GIL makes a
single counter += atomic, but histograms need multi-value consistency.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Any, Iterator

from fastapi import APIRouter
from fastapi.responses import PlainTextResponse


_lock = threading.Lock()

# --- counters -----------------------------------------------------------

_counters: dict[tuple[str, tuple[tuple[str, str], ...]], float] = {}


def counter(name: str, *, by: float = 1.0, **labels: str) -> None:
    """Increment a named counter by `by` (default 1)."""
    key = (name, tuple(sorted(labels.items())))
    with _lock:
        _counters[key] = _counters.get(key, 0.0) + by


# --- histograms ---------------------------------------------------------

_DEFAULT_BUCKETS: tuple[float, ...] = (
    0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0,
)


@dataclass
class _Histogram:
    buckets: tuple[float, ...]
    bucket_counts: list[int] = field(default_factory=list)
    count: int = 0
    total: float = 0.0

    def __post_init__(self) -> None:
        if not self.bucket_counts:
            self.bucket_counts = [0] * len(self.buckets)


_histograms: dict[tuple[str, tuple[tuple[str, str], ...]], _Histogram] = {}


def histogram(
    name: str,
    *,
    buckets: tuple[float, ...] | None = None,
    **labels: str,
) -> _Histogram:
    """Return (and lazily initialize) a histogram."""
    key = (name, tuple(sorted(labels.items())))
    with _lock:
        hist = _histograms.get(key)
        if hist is None:
            hist = _Histogram(buckets=buckets or _DEFAULT_BUCKETS)
            _histograms[key] = hist
    return hist


def observe(name: str, value: float, **labels: str) -> None:
    """Record one sample on the named histogram."""
    hist = histogram(name, **labels)
    with _lock:
        hist.count += 1
        hist.total += value
        for idx, bound in enumerate(hist.buckets):
            if value <= bound:
                hist.bucket_counts[idx] += 1


# --- rendering ----------------------------------------------------------


def _format_labels(labels: tuple[tuple[str, str], ...]) -> str:
    if not labels:
        return ""
    pairs = ",".join(f'{k}="{_escape(v)}"' for k, v in labels)
    return "{" + pairs + "}"


def _escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


def render_text() -> str:
    lines: list[str] = []
    with _lock:
        for (name, labels), value in sorted(_counters.items()):
            lines.append(f"# TYPE {name} counter")
            lines.append(f"{name}{_format_labels(labels)} {value}")
        for (name, labels), hist in sorted(_histograms.items()):
            lines.append(f"# TYPE {name} histogram")
            cumulative = 0
            for bound, cnt in zip(hist.buckets, hist.bucket_counts):
                cumulative += cnt
                bucket_labels = labels + (("le", _fmt(bound)),)
                lines.append(
                    f"{name}_bucket{_format_labels(bucket_labels)} {cumulative}"
                )
            inf_labels = labels + (("le", "+Inf"),)
            lines.append(f"{name}_bucket{_format_labels(inf_labels)} {hist.count}")
            lines.append(f"{name}_sum{_format_labels(labels)} {hist.total}")
            lines.append(f"{name}_count{_format_labels(labels)} {hist.count}")
    return "\n".join(lines) + "\n"


def _fmt(v: float) -> str:
    if v == int(v):
        return str(int(v))
    return f"{v:g}"


def reset() -> None:
    """Test helper — wipe every counter and histogram."""
    with _lock:
        _counters.clear()
        _histograms.clear()


def iter_counters() -> Iterator[tuple[str, dict[str, str], float]]:
    with _lock:
        snapshot = list(_counters.items())
    for (name, labels), value in snapshot:
        yield name, dict(labels), value


# --- FastAPI surface ----------------------------------------------------

metrics_router = APIRouter(tags=["ops"])


@metrics_router.get("/metrics", response_class=PlainTextResponse)
async def metrics_endpoint() -> Any:
    return render_text()
