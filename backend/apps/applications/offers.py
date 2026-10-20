"""Offer terms. Money comes from credit_math; the rate grid is a placeholder until D4.

decision-model.md (D4) will replace `rate_for` with the grade × product grid;
same grade can mean different terms for different products (case, «Скоринг ≠ решение»).
"""

from datetime import timedelta
from decimal import Decimal

from django.utils import timezone

from apps.applications.models import Application, Decision, Offer, OfferStatus
from apps.credit_math import annuity_payment, round_ratio
from apps.products.models import Product

OFFER_TTL = timedelta(days=30)  # D17
GRADE_POSITION = {"A": 0, "B": 1, "C": 2, "D": 3, "E": 4}


def rate_for(product: Product, grade: str | None) -> Decimal:
    """Linear from rate_min (grade A) to rate_max (grade E); unknown grade → rate_max."""
    if grade not in GRADE_POSITION:
        return product.rate_max
    share = Decimal(GRADE_POSITION[grade]) / Decimal(4)
    return round_ratio(product.rate_min + (product.rate_max - product.rate_min) * share)


def monthly_payment(product: Product, amount: Decimal, rate: Decimal, term: int) -> Decimal | None:
    """Revolving products (overdraft, factoring) have no fixed annuity payment."""
    if product.is_revolving:
        return None
    return annuity_payment(amount, rate, term)


def create_offer(
    application: Application,
    decision: Decision,
    *,
    product: Product,
    amount: Decimal,
    term_months: int,
    rate: Decimal,
    reasons: list[dict] | None = None,
) -> Offer:
    """New active offer; any previous active offer of the application is superseded."""
    Offer.objects.filter(application=application, status=OfferStatus.ACTIVE).update(
        status=OfferStatus.SUPERSEDED
    )
    return Offer.objects.create(
        decision=decision,
        application=application,
        product=product,
        amount=amount,
        requested_amount=application.requested_amount,
        term_months=term_months,
        rate=rate,
        monthly_payment=monthly_payment(product, amount, rate, term_months),
        is_counteroffer=(
            amount != application.requested_amount or term_months != application.term_months
        ),
        product_changed=application.product_id is not None and product.pk != application.product_id,
        reasons=reasons or [],
        expires_at=timezone.now() + OFFER_TTL,
    )


def current_offer(application: Application) -> Offer | None:
    """The active offer, or the accepted one after the client said yes."""
    return (
        application.offers.filter(status__in=(OfferStatus.ACTIVE, OfferStatus.ACCEPTED))
        .select_related("product")
        .first()
    )
