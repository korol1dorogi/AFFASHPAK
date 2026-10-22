"""Seams from the 22.10 architecture audit: submit ↔ pipeline, officer ↔ catalog, offer expiry."""

import uuid
from datetime import timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

from apps.applications.access import Actor
from apps.applications.models import (
    BKI_CONSENT_VERSION,
    ApplicationStatus,
    Decision,
    DecisionOutcome,
    Offer,
    OfferStatus,
)
from apps.applications.transitions import available_actions
from apps.core.factories import make_application
from apps.core.testing import assert_matches_contract

pytestmark = pytest.mark.django_db
S = ApplicationStatus
CONSENT = {"bki_consent": True, "consent_version": BKI_CONSENT_VERSION}


def submit(client, pk: int, body: dict | None = None):
    return client.post(
        f"/api/applications/{pk}/submit",
        body or CONSENT,
        format="json",
        HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4()),
    )


# ───────────────────────── submit: no gap the client cannot fix later ─────────────────────────


def test_submit_without_a_product_is_400_and_stays_a_draft(world):
    """After sending, fields can no longer change: a gap here would loop through info_requested."""
    application = make_application(world["company"], product=None, purpose="Деньги")
    path = f"/api/applications/{application.pk}/submit"
    response = submit(world["as_signatory"], application.pk)
    assert response.status_code == 400
    assert_matches_contract(response, method="post", path=path, request_body=CONSENT)
    assert set(response.json()["error"]["details"]) == {"product_code", "purpose"}
    application.refresh_from_db()
    assert application.status == S.DRAFT
    assert not application.events.filter(kind="consent_given").exists()


def test_submit_outside_the_product_term_is_400(world):
    application = make_application(world["company"], term_months=24)  # overdraft: 1–12
    response = submit(world["as_signatory"], application.pk)
    assert response.status_code == 400
    assert "term_months" in response.json()["error"]["details"]


def test_submit_checks_the_version_the_signatory_reviewed(world):
    application = make_application(world["company"])
    application.version = 3  # a preparer saved the draft meanwhile
    application.save(update_fields=["version"])
    body = {**CONSENT, "version": 2}
    response = submit(world["as_signatory"], application.pk, body)
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "version_conflict"
    assert (
        submit(world["as_signatory"], application.pk, {**CONSENT, "version": 3}).status_code == 200
    )


def test_a_preparer_gets_403_before_any_consent_check(world):
    application = make_application(world["company"])
    body = {"bki_consent": True, "consent_version": "outdated"}
    assert submit(world["as_preparer"], application.pk, body).status_code == 403


# ───────────────────────── the officer's offer stays inside the product ─────────────────────────


@pytest.mark.parametrize(
    ("field", "value"),
    [("amount", "50000.00"), ("term_months", 24), ("rate", "0.0100")],
)
def test_counteroffer_outside_the_product_is_400(world, field, value):
    application = make_application(world["company"], status=S.MANUAL_REVIEW)
    body = {
        "version": 0,
        "amount": "600000.00",
        "term_months": 6,
        "rate": "0.22",
        "comment": "Предлагаем другие условия",
        field: value,
    }
    path = f"/api/bank/applications/{application.pk}/counteroffer"
    response = world["as_bank"].post(path, body, format="json")
    assert response.status_code == 400
    assert field in response.json()["error"]["details"]
    assert not Decision.objects.filter(application=application).exists()


# ───────────────────────── an expired offer ─────────────────────────


def _expired_offer(world):
    application = make_application(world["company"], status=S.OFFER)
    decision = Decision.objects.create(
        application=application,
        outcome=DecisionOutcome.OFFER,
        decided_by="auto",
        policy_version="test",
    )
    Offer.objects.create(
        application=application,
        decision=decision,
        product=application.product,
        amount=Decimal("100000.00"),
        requested_amount=Decimal("100000.00"),
        term_months=12,
        rate=Decimal("0.20"),
        status=OfferStatus.ACTIVE,
        expires_at=timezone.now() - timedelta(days=1),
    )
    return application


def test_an_expired_offer_is_not_offered_and_answers_409(world):
    application = _expired_offer(world)
    actor = Actor(kind="client", user=world["signatory"], role="signatory")
    assert "accept_offer" not in available_actions(application, actor)
    path = f"/api/applications/{application.pk}/offer/accept"
    response = world["as_signatory"].post(path)
    assert response.status_code == 409
    assert_matches_contract(response, method="post", path=path)
