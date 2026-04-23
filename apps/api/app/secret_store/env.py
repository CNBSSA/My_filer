"""Env-var backed secrets provider (dev default)."""

from __future__ import annotations

import os
from typing import Mapping


class EnvSecretsProvider:
    """Reads secrets from `os.environ` (or an injected mapping for tests).

    Keys are matched **case-insensitively** against the underlying
    mapping so callers can pass `anthropic_api_key` or
    `ANTHROPIC_API_KEY` interchangeably.
    """

    name = "env"

    def __init__(self, env: Mapping[str, str] | None = None) -> None:
        self._env = env if env is not None else os.environ

    def get(self, key: str) -> str | None:
        if not key:
            return None
        upper = key.upper()
        # Fast path — exact match in either case.
        if upper in self._env:
            value = self._env[upper]
            return value or None
        if key in self._env:
            value = self._env[key]
            return value or None
        # Case-insensitive fallback.
        for existing_key, value in self._env.items():
            if existing_key.upper() == upper:
                return value or None
        return None
