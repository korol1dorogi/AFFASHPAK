"""Correlation context of the current request or Celery task (OPS5).

Every log record gets these fields (apps/core/logging.py): one request_id follows an
application from the client's request through the worker. Only ids live here, never data.
"""

import re
import uuid
from contextvars import ContextVar, Token
from typing import Any

request_id: ContextVar[str | None] = ContextVar("request_id", default=None)
application_id: ContextVar[int | None] = ContextVar("application_id", default=None)
user_id: ContextVar[int | None] = ContextVar("user_id", default=None)

_VARS: dict[str, ContextVar[Any]] = {
    "request_id": request_id,
    "application_id": application_id,
    "user_id": user_id,
}

# A client's X-Request-ID goes into the logs only in this shape: no spaces, newlines or quotes
# that could forge a log line or break the JSON.
_REQUEST_ID = re.compile(r"[A-Za-z0-9-]{8,64}")


def is_valid_request_id(value: object) -> bool:
    return isinstance(value, str) and _REQUEST_ID.fullmatch(value) is not None


def new_request_id(prefix: str = "") -> str:
    value = str(uuid.uuid4())
    return f"{prefix}-{value}" if prefix else value


def bind(**values: Any) -> list[tuple[ContextVar[Any], Token]]:
    """Set the given fields; reset() with the returned tokens restores what was there before."""
    return [(_VARS[name], _VARS[name].set(value)) for name, value in values.items()]


def reset(tokens: list[tuple[ContextVar[Any], Token]]) -> None:
    for var, token in reversed(tokens):
        var.reset(token)


def current() -> dict[str, Any]:
    return {name: var.get() for name, var in _VARS.items()}
