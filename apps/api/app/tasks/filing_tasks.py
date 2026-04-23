"""Filing submission tasks — the async face of `gateway.service`.

Rationale: the sync `submit_filing_to_nrs` already has the exact retry
shape NRS needs (2s / 4s / 8s / 16s) and the simulation fallback.
Moving to Celery doesn't change the logic — it relocates the retry
loop into a worker process so the HTTP request returns immediately.

When `CELERY_ENABLED=false`, nothing enqueues — callers in
`gateway.service.submit_filing_to_nrs` hit the sync path directly.
When true, they call `.delay()` and a worker picks the task up.
"""

from __future__ import annotations

import logging
from typing import Any

from app.celery_app import celery_app

log = logging.getLogger("mai_filer.tasks.filing")


@celery_app.task(
    name="mai_filer.filing.submit_to_nrs",
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=2,
    retry_backoff_max=16,
    retry_jitter=False,
    max_retries=3,
    acks_late=True,
)
def submit_filing_to_nrs_task(
    self,  # type: ignore[no-untyped-def]
    *,
    filing_id: str,
    language: str = "en",
) -> dict[str, Any]:
    """Async wrapper around `gateway.service.submit_filing_to_nrs`.

    Loads the filing, calls the sync service (which does signing, posts
    to NRS, and persists the receipt), returns the outcome dict so
    downstream callers / webhook listeners can pick it up via the
    result backend.
    """
    # Local imports — Celery pickles task arguments, so keep the module
    # surface small and import on-demand. Looking up `get_session` here
    # (rather than binding it at module-load) lets the test suite swap
    # in the in-memory SQLite session factory via monkeypatch.
    from app.db import session as db_session
    from app.db.models import Filing
    from app.gateway.service import SubmissionConfigError, submit_filing_to_nrs

    session_gen = db_session.get_session()
    session = next(session_gen)
    try:
        filing = session.get(Filing, filing_id)
        if filing is None:
            log.warning("submit_filing_to_nrs_task: filing %s not found", filing_id)
            return {"error": "filing not found", "filing_id": filing_id}
        try:
            outcome = submit_filing_to_nrs(
                session=session, filing=filing, language=language
            )
        except SubmissionConfigError as exc:
            log.info("submit_filing_to_nrs_task: not ready — %s", exc)
            return {"error": str(exc), "reason": "not_ready"}
        return outcome.to_dict()
    finally:
        session_gen.close()


__all__ = ["submit_filing_to_nrs_task"]
