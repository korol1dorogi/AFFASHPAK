"""Single error format for the whole API (openapi: components.schemas.Error).

{"error": {"code": "not_found", "message": "...", "details": {...}}}
"""

from typing import Any

from django.core.exceptions import PermissionDenied
from django.http import Http404
from rest_framework import exceptions
from rest_framework.response import Response
from rest_framework.views import exception_handler


def api_exception_handler(exc: Exception, context: dict[str, Any]) -> Response | None:
    if isinstance(exc, Http404):
        exc = exceptions.NotFound()
    elif isinstance(exc, PermissionDenied):
        exc = exceptions.PermissionDenied()

    response = exception_handler(exc, context)
    if response is None or not isinstance(exc, exceptions.APIException):
        return response

    if isinstance(exc, exceptions.ValidationError):
        message = "Проверьте введённые данные."
        details = exc.detail if isinstance(exc.detail, dict) else {"non_field_errors": exc.detail}
    else:
        message = str(exc.detail)
        details = None

    codes = exc.get_codes()
    code = codes if isinstance(codes, str) else exc.default_code
    body: dict[str, Any] = {"code": code, "message": message}
    if details is not None:
        body["details"] = details
    response.data = {"error": body}
    return response
