"""POST /api/recommendations and POST /api/applications/{id}/what-if (docs/openapi.yaml)."""

from rest_framework.permissions import BasePermission, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.applications.access import is_bank_user
from apps.recommendations.api import recommend_for_user, what_if_for_user


class IsClientUser(BasePermission):
    """Recommendations are for clients; bank staff get 403."""

    message = "Подбор доступен только клиентам."

    def has_permission(self, request: Request, view: object) -> bool:
        return not is_bank_user(request.user)


class RecommendationsView(APIView):
    permission_classes = (IsAuthenticated, IsClientUser)

    def post(self, request: Request) -> Response:
        return Response(recommend_for_user(request.user, request.data))


class WhatIfView(APIView):
    """calculateWhatIf: scoped to the user's company like every client application endpoint."""

    def post(self, request: Request, pk: int) -> Response:
        return Response(what_if_for_user(request.user, pk, request.data))
