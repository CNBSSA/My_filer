"""Shared rate-limiter instance for sensitive endpoints.

Import `limiter` and apply `@limiter.limit("N/minute")` to any route that
should be throttled. The SlowAPIMiddleware and exception handler are wired in
`app/main.py`.
"""

from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
