"""Fix 3.2: a client who accepted the offer can still walk away before signing."""

import pytest

from apps.applications import services
from apps.applications.models import ApplicationStatus, DecisionOutcome, Offer
from apps.core.factories import make_application
from apps.core.testing import assert_matches_contract

pytestmark = pytest.mark.django_db
S = ApplicationStatus


def _signing(world):
    """Offer accepted, signature code issued: the client is one step from signing."""
    application = make_application(world["company"], status=S.PROCESSING, product=world["loan"])
    services.record_auto_decision(
        application.pk,
        outcome=DecisionOutcome.OFFER,
        grade="A",
        policy_version="test",
        reasons=[],
        offer={
            "product": world["loan"],
            "amount": application.requested_amount,
            "term_months": application.term_months,
            "rate": world["loan"].rate_min,
        },
    )
    pk = application.pk
    world["as_signatory"].post(f"/api/applications/{pk}/offer/accept")
    code = world["as_signatory"].post(f"/api/applications/{pk}/signature").json()["code"]
    return pk, code


def test_cancel_is_offered_while_signing(world):
    pk, _ = _signing(world)
    actions = world["as_signatory"].get(f"/api/applications/{pk}").json()["available_actions"]
    assert actions == ["sign", "cancel"]
    preparer = world["as_preparer"].get(f"/api/applications/{pk}").json()["available_actions"]
    assert "cancel" not in preparer


def test_the_signatory_cancels_before_signing_and_the_offer_is_declined(world):
    pk, code = _signing(world)
    path = f"/api/applications/{pk}/cancel"
    response = world["as_signatory"].post(path)

    assert response.status_code == 200
    assert_matches_contract(response, method="post", path=path)
    assert response.json()["status"] == "cancelled"
    assert response.json()["available_actions"] == []
    assert Offer.objects.get(application_id=pk).status == "declined"
    # The code shown before is no good any more: nothing to sign.
    late = world["as_signatory"].post(
        f"/api/applications/{pk}/signature/confirm", {"code": code}, format="json"
    )
    assert late.status_code == 409


def test_the_preparer_cannot_cancel_while_signing(world):
    pk, _ = _signing(world)
    assert world["as_preparer"].post(f"/api/applications/{pk}/cancel").status_code == 403


def test_once_signed_it_cannot_be_cancelled(world):
    pk, code = _signing(world)
    world["as_signatory"].post(
        f"/api/applications/{pk}/signature/confirm", {"code": code}, format="json"
    )
    response = world["as_signatory"].post(f"/api/applications/{pk}/cancel")
    assert response.status_code == 409
    assert Offer.objects.get(application_id=pk).status == "accepted"
