"""Celery app (P6.4).

Everything in `app/tasks/` is auto-registered. The app is a no-op when
`CELERY_ENABLED=false` (the default) — callers that would dispatch via
`.delay()` check the flag and run inline instead, so dev / CI / local
dev all work without Redis.

Production wires `CELERY_ENABLED=true` + `CELERY_BROKER_URL` to an
ElastiCache Redis (per the AWS checklist) and a companion worker
process runs `celery -A app.celery_app worker`.
"""

from __future__ import annotations

import logging

from celery import Celery

from app.config import get_settings

log = logging.getLogger("mai_filer.celery")


def build_celery_app() -> Celery:
    settings = get_settings()
    app = Celery(
        "mai_filer",
        broker=settings.celery_broker_url,
        backend=settings.celery_result_backend or settings.celery_broker_url,
        include=["app.tasks.filing_tasks"],
    )
    # In eager mode, task.delay(...) executes synchronously in the caller
    # process — exactly how the pre-Celery gateway behaved. Tests set
    # this unconditionally; at runtime it follows `celery_task_eager`.
    app.conf.update(
        task_always_eager=settings.celery_task_eager,
        task_eager_propagates=True,
        task_acks_late=True,
        task_reject_on_worker_lost=True,
        worker_prefetch_multiplier=1,
        task_soft_time_limit=120,
        task_time_limit=180,
        broker_connection_retry_on_startup=True,
    )
    return app


celery_app = build_celery_app()


def is_async_enabled() -> bool:
    """True iff dispatches should actually enqueue instead of running inline."""
    s = get_settings()
    return s.celery_enabled and not s.celery_task_eager


__all__ = ["build_celery_app", "celery_app", "is_async_enabled"]
