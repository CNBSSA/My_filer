"""JSON structured logging.

One-line JSON per record with stable keys: `ts`, `level`, `logger`,
`message`, `correlation_id` (when bound), plus any `extra={...}` the
caller passes. Keeps logs grep-friendly and pipeline-friendly
(CloudWatch Logs Insights / Athena).
"""

from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone
from typing import Any

# Keys `logging` sets on every LogRecord. Anything NOT in here is
# treated as an `extra` field the caller attached and is emitted
# under the record's top-level JSON.
_STANDARD_ATTRS = frozenset(
    {
        "name", "msg", "args", "levelname", "levelno", "pathname",
        "filename", "module", "exc_info", "exc_text", "stack_info",
        "lineno", "funcName", "created", "msecs", "relativeCreated",
        "thread", "threadName", "processName", "process",
        "taskName",
    }
)


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Correlation ID is read inside the formatter so any logger in the
        # process automatically carries it without needing filters.
        from app.observability.correlation import current_correlation_id

        cid = current_correlation_id()
        if cid:
            payload["correlation_id"] = cid

        for key, value in record.__dict__.items():
            if key in _STANDARD_ATTRS:
                continue
            if key.startswith("_"):
                continue
            payload[key] = value

        if record.exc_info:
            payload["exc_type"] = record.exc_info[0].__name__ if record.exc_info[0] else None
            payload["exc_text"] = self.formatException(record.exc_info)

        return json.dumps(payload, ensure_ascii=False, default=str)


def configure_json_logging(*, level: str = "INFO") -> None:
    """Install a JSON stdout handler on the root logger.

    Idempotent — calling twice replaces the root handlers each time.
    """
    handler = logging.StreamHandler(stream=sys.stdout)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    for existing in list(root.handlers):
        root.removeHandler(existing)
    root.addHandler(handler)
    root.setLevel(level.upper())
