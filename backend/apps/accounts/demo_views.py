"""Demo personas, quick sign-in and simulator outages (docs/openapi.yaml, tag `demo`).

Everything here is 404 unless DEMO_MODE=1.
"""

from django.conf import settings
from django.contrib.auth import login
from django.contrib.auth.models import User
from rest_framework import serializers, status
from rest_framework.exceptions import NotFound
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from apps.accounts.demo import available_personas, reset_demo
from apps.accounts.serializers import me_data
from apps.core.authentication import enforce_csrf
from apps.core.permissions import IsBankUser
from apps.integrations import flags

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
    # Only its own scope: the per-IP anonymous limit would cut a jury switching personas.
    throttle_classes = (ScopedRateThrottle,)
    throttle_scope = "demo_login"

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


class DemoFailuresSerializer(serializers.Serializer):
    """DemoFailures: every source is required, unknown keys are rejected."""

    egrul = serializers.BooleanField()
    transparent_business = serializers.BooleanField()
    bki = serializers.BooleanField()
    bank_account = serializers.BooleanField()

    def to_internal_value(self, data):
        unknown = set(data) - set(self.fields) if hasattr(data, "keys") else set()
        if unknown:
            raise serializers.ValidationError({key: ["Неизвестный источник."] for key in unknown})
        return super().to_internal_value(data)


class DemoFailuresView(_DemoView):
    """Scenario 7: a bank user switches a simulator off; the next applications see the outage."""

    permission_classes = (IsBankUser,)

    def get(self, request: Request) -> Response:
        return Response(flags.current())

    def put(self, request: Request) -> Response:
        serializer = DemoFailuresSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        for source, failing in serializer.validated_data.items():
            flags.set_failing(source, failing)
        return Response(flags.current())


class DemoResetView(_DemoView):
    """POST /api/demo/reset: back to the seeded state between demo runs (bank user).

    Applications (with their files), notifications and outage flags go; the catalog, personas
    and the demo queue are seeded again. Accounts people registered stay.
    """

    permission_classes = (IsBankUser,)

    def post(self, request: Request) -> Response:
        reset_demo()
        return Response(status=status.HTTP_204_NO_CONTENT)
