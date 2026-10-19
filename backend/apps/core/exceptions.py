"""Single error format for the whole API (openapi: components.schemas.Error).

{"error": {"code": "not_found", "message": "...", "details": {...}}}
"""

from typing import Any

from django.core.exceptions import PermissionDenied, RequestDataTooBig
from django.http import Http404, HttpRequest, HttpResponse, JsonResponse
from rest_framework import exceptions, status
from rest_framework.response import Response
from rest_framework.views import exception_handler


def api_exception_handler(exc: Exception, context: dict[str, Any]) -> Response | None:
    if isinstance(exc, RequestDataTooBig):
        return Response(
            {
                "error": {
                    "code": "payload_too_large",
                    "message": "Файл больше допустимого размера.",
                }
            },
            status=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
        )

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


def not_found_view(request: HttpRequest, exception: Exception) -> HttpResponse:
    """handler404: unknown URLs also answer in the single error format (DEBUG=False)."""
    return JsonResponse({"error": {"code": "not_found", "message": "Не найдено."}}, status=404)


def server_error_view(request: HttpRequest) -> HttpResponse:
    """handler500: no stack traces or HTML, just the single error format."""
    return JsonResponse(
        {"error": {"code": "server_error", "message": "Внутренняя ошибка. Попробуйте позже."}},
        status=500,
    )
