from rest_framework.authentication import CSRFCheck
from rest_framework.authentication import SessionAuthentication as DrfSessionAuthentication
from rest_framework.exceptions import PermissionDenied
from rest_framework.request import Request

CSRF_FAILED = "Не прошла проверка безопасности. Обновите страницу и попробуйте снова."


class SessionAuthentication(DrfSessionAuthentication):
    def authenticate_header(self, request):
        """Keep a missing session at 401, matching the contract.

        DRF turns NotAuthenticated into 403 when no challenge header is set.
        Session login has no browser prompt; the value only preserves the status.
        """
        return "Session"

    def enforce_csrf(self, request):
        try:
            super().enforce_csrf(request)
        except PermissionDenied as exc:
            raise PermissionDenied(CSRF_FAILED) from exc


def enforce_csrf(request: Request) -> None:
    """CSRF for anonymous unsafe requests (login, register, demo login).

    DRF checks CSRF only for an authenticated session, so login CSRF needs this explicitly.
    """
    check = CSRFCheck(lambda _request: None)
    check.process_request(request._request)
    if check.process_view(request._request, None, (), {}) is not None:
        raise PermissionDenied(CSRF_FAILED)
