"""Entry point for the view and the assistant tool `recommend_products` (AI1).

Acts on behalf of the user: their company only, input validated by the same serializer.
"""

from datetime import date

from django.contrib.auth.models import AbstractBaseUser
from django.utils import timezone
from rest_framework.exceptions import NotFound, ValidationError

from apps.applications.access import (
    NOT_FOUND,
    current_membership,
    get_client_application,
    is_bank_user,
)
from apps.core.exceptions import Conflict
from apps.recommendations.serializers import (
    RecommendationRequestSerializer,
    RecommendationResultSerializer,
    WhatIfRequestSerializer,
    WhatIfResultSerializer,
)
from apps.recommendations.service import (
    RecommendationInput,
    TermOutOfRange,
    WhatIfUnavailable,
    recommend,
    what_if,
)


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


def what_if_for_user(
    user: AbstractBaseUser, application_id: int, payload: object, *, on_date: date | None = None
) -> dict:
    """WhatIfResult for an application of the user's company (XP1).

    Another company's application (or a bank user) → 404, as every client endpoint; no active
    offer with a fixed payment → 409; bad input or a term outside the product → 400.
    """
    application = get_client_application(user, application_id)
    serializer = WhatIfRequestSerializer(data=payload)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data
    try:
        result = what_if(
            application,
            data["amount"],
            data["term_months"],
            on_date=on_date or timezone.localdate(),
        )
    except WhatIfUnavailable as error:
        raise Conflict(error.message, code=error.code) from error
    except TermOutOfRange as error:
        raise ValidationError({"term_months": [str(error)]}) from error
    return WhatIfResultSerializer(result).data
