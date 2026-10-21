"""Company input (docs/openapi.yaml, tag `company`). Output reuses CompanySerializer and
MemberSerializer from apps/applications/serializers.py, which the bank card also uses."""

from rest_framework import serializers

from apps.business.inn import inn_is_valid
from apps.business.models import MemberRole

INN = r"^\d{10}(\d{2})?$"
INN_MESSAGE = "ИНН — 10 цифр у ООО или 12 у ИП."
INN_CHECKSUM_MESSAGE = "В ИНН ошибка: не сходятся контрольные цифры. Проверьте номер."


class InnSerializer(serializers.Serializer):
    inn = serializers.RegexField(INN, error_messages={"invalid": INN_MESSAGE})

    def validate_inn(self, value: str) -> str:
        if not inn_is_valid(value):
            raise serializers.ValidationError(INN_CHECKSUM_MESSAGE)
        return value


class CompanyUpdateSerializer(serializers.Serializer):
    """Only the interface label; the registry requisites (name included) never change here."""

    short_name = serializers.CharField(max_length=300, allow_blank=True, allow_null=True)


class MemberCreateSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=150)
    role = serializers.ChoiceField(choices=MemberRole.choices)
    position = serializers.CharField(max_length=100)
