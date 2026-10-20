"""Demo personas and quick sign-in (docs/openapi.yaml, tag `demo`). 404 unless DEMO_MODE=1.

Failures and reset (/api/demo/failures, /api/demo/reset) belong to B7/L5.
"""

from django.conf import settings
from django.contrib.auth import login
from django.contrib.auth.models import User
from rest_framework import serializers
from rest_framework.exceptions import NotFound
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.demo import available_personas
from apps.accounts.serializers import me_data
from apps.core.authentication import enforce_csrf

NOT_FOUND = "Не найдено."


class DemoLoginSerializer(serializers.Serializer):
    persona = serializers.CharField(max_length=64)


class _DemoView(APIView):
    permission_classes = (AllowAny,)

    def initial(self, request: Request, *args, **kwargs) -> None:
        if not settings.DEMO_MODE:
            raise NotFound(NOT_FOUND)
        super().initial(request, *args, **kwargs)


class DemoPersonasView(_DemoView):
    def get(self, request: Request) -> Response:
        return Response(available_personas())


class DemoLoginView(_DemoView):
    throttle_scope = "login"

    def post(self, request: Request) -> Response:
        enforce_csrf(request)
        serializer = DemoLoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        code = serializer.validated_data["persona"]
        persona = next((p for p in available_personas() if p["code"] == code), None)
        if persona is None:
            raise NotFound("Такой демо-персоны нет. Обновите страницу.")
        user = User.objects.get(username=persona["username"])
        login(request._request, user, backend="django.contrib.auth.backends.ModelBackend")
        return Response(me_data(user))
