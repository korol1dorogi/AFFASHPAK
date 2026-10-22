"""Company input and invitations (docs/openapi.yaml, tag `company`). Company and member output
reuses CompanySerializer and MemberSerializer from apps/applications/serializers.py, which the
bank card also uses."""

from django.contrib.auth.validators import UnicodeUsernameValidator
from rest_framework import serializers

from apps.applications.serializers import user_ref
from apps.business.inn import inn_is_valid
from apps.business.models import Invitation, MemberRole

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


class InvitationCreateSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=150, validators=[UnicodeUsernameValidator()])
    role = serializers.ChoiceField(choices=MemberRole.choices)
    position = serializers.CharField(max_length=100)


# ───────────────────────── output ─────────────────────────


class InvitationSerializer(serializers.ModelSerializer):
    """The company's own pending invitation, as the signatory typed it."""

    class Meta:
        model = Invitation
        fields = ("id", "username", "role", "position", "created_at")
        read_only_fields = fields


class IncomingInvitationSerializer(serializers.ModelSerializer):
    """An invitation addressed to the current user: who invites, into what and as whom."""

    company = serializers.SerializerMethodField()
    invited_by = serializers.SerializerMethodField()

    class Meta:
        model = Invitation
        fields = ("id", "company", "role", "position", "invited_by", "created_at")
        read_only_fields = fields

    def get_company(self, invitation: Invitation) -> dict:
        company = invitation.company
        return {
            "id": company.pk,
            "name": company.name,
            "short_name": company.short_name or None,
            "legal_form": company.legal_form,
            "inn": company.inn,
        }

    def get_invited_by(self, invitation: Invitation) -> dict | None:
        return user_ref(invitation.invited_by)
