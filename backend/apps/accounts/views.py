"""Session auth: csrf, register, login, logout, me (docs/openapi.yaml, tag `auth`).

Sessions + CSRF on one origin. Login and register are anonymous, so CSRF is checked
explicitly (DRF checks it only for an existing session).
"""

from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.db import transaction
from django.middleware.csrf import get_token
from rest_framework import status
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import UserKind, UserProfile
from apps.accounts.serializers import LoginSerializer, RegisterSerializer, me_data
from apps.core.authentication import enforce_csrf

INVALID_CREDENTIALS = "Неверный логин или пароль."


class CsrfView(APIView):
    permission_classes = (AllowAny,)

    def get(self, request: Request) -> Response:
        return Response({"csrf_token": get_token(request._request)})


class RegisterView(APIView):
    permission_classes = (AllowAny,)
    throttle_scope = "login"

    def post(self, request: Request) -> Response:
        enforce_csrf(request)
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        with transaction.atomic():
            user = User.objects.create_user(data["username"], password=data["password"])
            UserProfile.objects.create(user=user, kind=UserKind.CLIENT, full_name=data["full_name"])
        login(request._request, user, backend="django.contrib.auth.backends.ModelBackend")
        return Response(me_data(user), status=status.HTTP_201_CREATED)


class LoginView(APIView):
    permission_classes = (AllowAny,)
    throttle_scope = "login"

    def post(self, request: Request) -> Response:
        enforce_csrf(request)
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = authenticate(request._request, **serializer.validated_data)
        if user is None:
            raise AuthenticationFailed(INVALID_CREDENTIALS, code="invalid_credentials")
        login(request._request, user)
        return Response(me_data(user))


class LogoutView(APIView):
    permission_classes = (AllowAny,)

    def post(self, request: Request) -> Response:
        logout(request._request)
        return Response(status=status.HTTP_204_NO_CONTENT)


class MeView(APIView):
    def get(self, request: Request) -> Response:
        return Response(me_data(request.user))
