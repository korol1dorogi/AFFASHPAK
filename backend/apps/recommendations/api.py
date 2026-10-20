"""Entry point for the view and the assistant tool `get_recommendations` (S7).

Acts on behalf of the user: their company only, input validated by the same serializer.
"""

from datetime import date

from django.contrib.auth.models import AbstractBaseUser
from django.utils import timezone
from rest_framework.exceptions import NotFound

from apps.applications.access import NOT_FOUND, current_membership, is_bank_user
from apps.recommendations.serializers import (
    RecommendationRequestSerializer,
    RecommendationResultSerializer,
)
from apps.recommendations.service import RecommendationInput, recommend


def recommend_for_user(
    user: AbstractBaseUser, payload: object, *, on_date: date | None = None
) -> dict:
    """RecommendationResult as a dict. No company of the user → NotFound; bad input → 400."""
    membership = current_membership(user) if not is_bank_user(user) else None
    if membership is None:
        raise NotFound(NOT_FOUND)
    serializer = RecommendationRequestSerializer(data=payload)
    serializer.is_valid(raise_exception=True)
    result = recommend(
        membership.company,
        RecommendationInput(**serializer.validated_data),
        on_date=on_date or timezone.localdate(),
    )
    return RecommendationResultSerializer(result).data
