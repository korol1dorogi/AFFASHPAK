"""Auth input and the Me payload (docs/openapi.yaml, tag `auth`)."""

from django.contrib.auth.models import AbstractBaseUser, User
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.validators import UnicodeUsernameValidator
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from apps.accounts.models import UserKind
from apps.applications.access import current_membership, user_kind
from apps.applications.serializers import user_ref


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=150)
    password = serializers.CharField(max_length=128, trim_whitespace=False)


class RegisterSerializer(serializers.Serializer):
    username = serializers.CharField(
        min_length=3, max_length=150, validators=[UnicodeUsernameValidator()]
    )
    password = serializers.CharField(min_length=8, max_length=128, trim_whitespace=False)
    full_name = serializers.CharField(max_length=200)

    def validate_username(self, value: str) -> str:
        if User.objects.filter(username__iexact=value).exists():
            raise serializers.ValidationError("Этот логин уже занят.")
        return value

    def validate(self, attrs: dict) -> dict:
        """One message at a time — the first check that fails, in the order of
        AUTH_PASSWORD_VALIDATORS: a list of four complaints at once reads as noise."""
        try:
            validate_password(attrs["password"], user=User(username=attrs["username"]))
        except DjangoValidationError as exc:
            raise serializers.ValidationError({"password": exc.messages[:1]}) from exc
        return attrs


def me_data(user: AbstractBaseUser) -> dict:
    kind = user_kind(user)
    membership = current_membership(user) if kind == UserKind.CLIENT else None
    profile = getattr(user, "profile", None)
    return {
        "id": user.pk,
        "username": user.get_username(),
        "full_name": user_ref(user)["full_name"],
        "kind": kind,
        "company_id": membership.company_id if membership else None,
        "company_role": membership.role if membership else None,
        "is_demo": bool(profile and profile.is_demo),
    }
