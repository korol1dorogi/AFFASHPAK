from rest_framework.permissions import BasePermission
from rest_framework.request import Request

from apps.applications.access import is_bank_user


class IsBankUser(BasePermission):
    """Bank workplace endpoints (/api/bank/*): clients get 403."""

    message = "Раздел доступен только сотрудникам банка."

    def has_permission(self, request: Request, view: object) -> bool:
        return bool(request.user and request.user.is_authenticated and is_bank_user(request.user))
