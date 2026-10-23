"""Correlation id and the access log (OPS5).

First in MIDDLEWARE: everything logged while the request runs — other middleware, the view, the
pipeline started on commit, a 500 — carries its request_id. The id comes back in X-Request-ID
and travels into the Celery worker with the task headers (config/celery.py).
"""

import logging
import re
import time
from collections.abc import Callable

from django.http import HttpRequest, HttpResponse

from apps.core import context

HEADER = "X-Request-ID"
access_logger = logging.getLogger("apps.core.access")

# /api/applications/<pk>… and /api/bank/applications/<pk>…: the pk is the application's id
_APPLICATION_PK = re.compile(r"^/api/(bank/)?applications/\d+(/|$)")
# Healthchecks poll these every few seconds: at INFO they would drown the application's history.
_QUIET_PATHS = frozenset({"/api/health", "/api/ready"})


def application_id_from(path: str, view_kwargs: dict) -> int | None:
    value = view_kwargs.get("application_id")
    if value is None and _APPLICATION_PK.match(path):
        value = view_kwargs.get("pk")
    return value if isinstance(value, int) else None


class RequestIdMiddleware:
    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        incoming = request.headers.get(HEADER)
        request_id = incoming if context.is_valid_request_id(incoming) else context.new_request_id()
        tokens = context.bind(request_id=request_id, application_id=None, user_id=None)
        started = time.monotonic()
        status = 500
        try:
            response = self.get_response(request)
            status = response.status_code
            response[HEADER] = request_id
            return response
        finally:
            self._access(request, status, started)
            context.reset(tokens)

    def process_view(self, request: HttpRequest, view_func, view_args, view_kwargs) -> None:
        # Runs after every process_request: the session user is known by now.
        user = getattr(request, "user", None)
        context.bind(
            application_id=application_id_from(request.path, view_kwargs),
            user_id=user.pk if user is not None and user.is_authenticated else None,
        )

    def _access(self, request: HttpRequest, status: int, started: float) -> None:
        if status >= 500:
            level = logging.ERROR
        elif request.path in _QUIET_PATHS:
            level = logging.DEBUG
        else:
            level = logging.INFO
        # request.path: no query string — the bank queue searches by INN in it. A decoded %0A
        # must not start a forged line in the text format.
        path = "".join(char if char.isprintable() else "?" for char in request.path)
        access_logger.log(
            level,
            "%s %s %s",
            request.method,
            path,
            status,
            extra={
                "method": request.method,
                "path": path,
                "status": status,
                "duration_ms": round((time.monotonic() - started) * 1000, 1),
            },
        )
