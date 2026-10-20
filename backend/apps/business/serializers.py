"""Company input (docs/openapi.yaml, tag `company`). Output reuses CompanySerializer and
MemberSerializer from apps/applications/serializers.py, which the bank card also uses."""

from rest_framework import serializers

from apps.business.models import MemberRole

INN = r"^\d{10}(\d{2})?$"
INN_MESSAGE = "ИНН — 10 цифр у ООО или 12 у ИП."


class InnSerializer(serializers.Serializer):
    inn = serializers.RegexField(INN, error_messages={"invalid": INN_MESSAGE})


class CompanyUpdateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=300)


class MemberCreateSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=150)
    role = serializers.ChoiceField(choices=MemberRole.choices)
    position = serializers.CharField(max_length=100)
