"""Object storage adapters for Mai Filer uploads.

Two implementations ship with v1:

  * `InMemoryStorage` — dict-backed; used by tests and as a safe fallback.
  * `LocalDiskStorage` — writes under a configurable root directory; used by
    local dev before MinIO/Nigerian-hosted S3 is configured.

Per ADR-0004 consequences in `COMPLIANCE.md §4`, production storage must
reside **inside Nigeria** (Galaxy Backbone / Rack Centre S3-compatible).
The production adapter will land in the gateway / infra phase; the
interface is stable now so swapping vendors is a one-file change.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


@dataclass(frozen=True)
class StoredBlob:
    """Metadata returned when content is persisted."""

    key: str
    size_bytes: int
    content_type: str


class StorageAdapter(Protocol):
    """Minimal object-storage surface Mai Filer depends on."""

    def put(self, content: bytes, *, content_type: str, filename: str | None = None) -> StoredBlob:
        """Persist `content` and return a `StoredBlob` with the assigned key."""

    def get(self, key: str) -> bytes:
        """Fetch the bytes previously persisted under `key`."""

    def delete(self, key: str) -> None:
        """Remove the object. Idempotent."""


class InMemoryStorage:
    """Dict-backed storage for tests and ephemeral scripts."""

    def __init__(self) -> None:
        self._blobs: dict[str, tuple[bytes, str]] = {}

    def put(
        self, content: bytes, *, content_type: str, filename: str | None = None
    ) -> StoredBlob:
        key = f"mem/{uuid.uuid4()}"
        self._blobs[key] = (content, content_type)
        return StoredBlob(key=key, size_bytes=len(content), content_type=content_type)

    def get(self, key: str) -> bytes:
        if key not in self._blobs:
            raise KeyError(f"unknown storage key: {key}")
        return self._blobs[key][0]

    def delete(self, key: str) -> None:
        self._blobs.pop(key, None)


class LocalDiskStorage:
    """Writes to `root/<uuid>` on the local filesystem. Dev-only."""

    def __init__(self, root: str | Path) -> None:
        self._root = Path(root)
        self._root.mkdir(parents=True, exist_ok=True)

    def put(
        self, content: bytes, *, content_type: str, filename: str | None = None
    ) -> StoredBlob:
        key = f"disk/{uuid.uuid4()}"
        path = self._root / key.split("/", 1)[1]
        path.write_bytes(content)
        return StoredBlob(key=key, size_bytes=len(content), content_type=content_type)

    def get(self, key: str) -> bytes:
        path = self._root / key.split("/", 1)[1]
        if not path.exists():
            raise KeyError(f"unknown storage key: {key}")
        return path.read_bytes()

    def delete(self, key: str) -> None:
        path = self._root / key.split("/", 1)[1]
        if path.exists():
            path.unlink()


# ---------------------------------------------------------------------------
# Module-level singleton for the default storage (DI-friendly).
# ---------------------------------------------------------------------------

_default_storage: StorageAdapter | None = None


def set_default_storage(storage: StorageAdapter) -> None:
    """Register the storage adapter used by the document service."""
    global _default_storage
    _default_storage = storage


def get_default_storage() -> StorageAdapter:
    """Return the active storage adapter. Tests override via `set_default_storage`.

    When no storage has been registered we hand out an InMemoryStorage — safe
    for dev, obviously not for prod (the compliance check in CI will catch it).
    """
    global _default_storage
    if _default_storage is None:
        _default_storage = InMemoryStorage()
    return _default_storage
