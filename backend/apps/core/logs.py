"""Log format (OPS5): one JSON object per line, or plain text (LOG_FORMAT=json|text).

ContextFilter stamps every record — the API's and the Celery worker's — with the correlation
fields from apps/core/context.py. Only whitelisted technical fields reach the output: no request
bodies, cookies, tokens, names, INNs or amounts (docs/security.md).
"""

import json
import logging
from datetime import UTC, datetime

from apps.core import context

CONTEXT_FIELDS = ("request_id", "application_id", "user_id")
# Fields a log call may pass in `extra=`; anything else in `extra` is not written.
EXTRA_FIELDS = (
    "method",
    "path",
    "status",
    "duration_ms",
    "event_id",
    "kind",
    "from_status",
    "to_status",
    "actor_kind",
    "source",
    "check_status",
    "task",
    "task_id",
)


class ContextFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        for name, value in context.current().items():
            # an explicit extra= wins: the journal line names its own application
            if getattr(record, name, None) is None:
                setattr(record, name, value)
        return True


def _timestamp(record: logging.LogRecord) -> str:
    moment = datetime.fromtimestamp(record.created, UTC)
    return moment.isoformat(timespec="milliseconds").replace("+00:00", "Z")


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        entry: dict[str, object] = {
            "ts": _timestamp(record),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for name in (*CONTEXT_FIELDS, *EXTRA_FIELDS):
            value = getattr(record, name, None)
            if value is not None:
                entry[name] = value
        if record.exc_info:
            entry["exc"] = self.formatException(record.exc_info)
        elif record.exc_text:
            entry["exc"] = record.exc_text
        if record.stack_info:
            entry["stack"] = self.formatStack(record.stack_info)
        return json.dumps(entry, ensure_ascii=False, default=str)


class TextFormatter(logging.Formatter):
    """For a human at a terminal: the same correlation fields, in brackets."""

    def __init__(self) -> None:
        super().__init__(
            "%(asctime)s %(levelname)s %(name)s "
            "[rid=%(request_id)s app=%(application_id)s user=%(user_id)s] %(message)s",
            defaults=dict.fromkeys(CONTEXT_FIELDS),
        )
