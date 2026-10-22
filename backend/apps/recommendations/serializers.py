"""RecommendationRequest and RecommendationResult of docs/openapi.yaml: explicit fields only."""

from decimal import Decimal

from rest_framework import serializers

from apps.applications.models import NeedType
from apps.products.serializers import ProductSerializer

UNKNOWN_FIELD = "Неизвестное поле."
INVOICE_REQUIRED = "Укажите сумму отгрузки по документу."
MONEY = {"max_digits": 14, "decimal_places": 2, "min_value": Decimal("0.01")}


class RecommendationRequestSerializer(serializers.Serializer):
    need_type = serializers.ChoiceField(choices=NeedType.choices)
    amount = serializers.DecimalField(**MONEY, required=False)
    term_months = serializers.IntegerField(min_value=1, max_value=360, required=False)
    invoice_amount = serializers.DecimalField(**MONEY, required=False)

    def validate(self, attrs: dict) -> dict:
        unknown = sorted(set(self.initial_data) - set(self.fields))
        if unknown:  # contract: additionalProperties: false
            raise serializers.ValidationError({name: [UNKNOWN_FIELD] for name in unknown})
        if attrs["need_type"] == NeedType.RECEIVABLE_DELAY and "invoice_amount" not in attrs:
            raise serializers.ValidationError({"invoice_amount": [INVOICE_REQUIRED]})
        return attrs


class DecimalStringField(serializers.Field):
    """Money, Rate and DecimalString: a plain decimal string, never an exponent."""

    def to_representation(self, value: Decimal) -> str:
        return format(value, "f")


class ReasonSerializer(serializers.Serializer):
    metric = serializers.CharField()
    value = DecimalStringField(allow_null=True)
    threshold = DecimalStringField(allow_null=True)
    passed = serializers.BooleanField()
    message = serializers.CharField()


class RecommendedOfferSerializer(serializers.Serializer):
    rank = serializers.IntegerField()
    product = ProductSerializer()
    amount = DecimalStringField()
    term_months = serializers.IntegerField()
    rate = DecimalStringField()
    monthly_payment = DecimalStringField(allow_null=True)
    fits = serializers.BooleanField()
    reasons = ReasonSerializer(many=True)


class RecommendationResultSerializer(serializers.Serializer):
    need_type = serializers.CharField()
    offers = RecommendedOfferSerializer(many=True)
    stop_factors = ReasonSerializer(many=True)
    is_preliminary = serializers.BooleanField()


class WhatIfRequestSerializer(serializers.Serializer):
    """WhatIfRequest: the term range of the product is checked by the service (400 term_months)."""

    amount = serializers.DecimalField(**MONEY)
    term_months = serializers.IntegerField(min_value=1, max_value=360)

    def validate(self, attrs: dict) -> dict:
        unknown = sorted(set(self.initial_data) - set(self.fields))
        if unknown:  # contract: additionalProperties: false
            raise serializers.ValidationError({name: [UNKNOWN_FIELD] for name in unknown})
        return attrs


class WhatIfResultSerializer(serializers.Serializer):
    amount = DecimalStringField()
    term_months = serializers.IntegerField()
    rate = DecimalStringField()
    monthly_payment = DecimalStringField()
    max_amount = DecimalStringField(allow_null=True)
    dscr_after = DecimalStringField(allow_null=True)
    min_dscr = DecimalStringField()
    fits = serializers.BooleanField()
    reasons = ReasonSerializer(many=True)
