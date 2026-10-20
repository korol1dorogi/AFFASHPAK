"""Client application API: contract, roles, idempotency, locking and the plan's scenarios."""

import uuid
from decimal import Decimal

import pytest

from apps.applications import services
from apps.applications.models import (
    ApplicationEvent,
    ApplicationStatus,
    DecisionOutcome,
    InfoRequest,
    Signature,
)
from apps.core.factories import make_application
from apps.core.testing import assert_matches_contract
from apps.notifications.models import Notification

S = ApplicationStatus


def submit(client, pk: int, key: str | None = None):
    headers = {"HTTP_IDEMPOTENCY_KEY": key or str(uuid.uuid4())}
    return client.post(f"/api/applications/{pk}/submit", **headers)


def offer_terms(product, amount="100000.00", term=12, rate="0.20"):
    return {
        "product": product,
        "amount": Decimal(amount),
        "term_months": term,
        "rate": Decimal(rate),
    }


def reason(metric="dscr", value="1.4000", threshold="1.25", passed=True):
    return {
        "metric": metric,
        "value": value,
        "threshold": threshold,
        "passed": passed,
        "message": "демо",
    }


# ───────────────────────── create, read, edit ─────────────────────────


def test_create_list_and_get_match_contract(world):
    body = {
        "need_type": "cash_gap",
        "purpose": "Зарплата до поступления оплаты",
        "requested_amount": "900000.00",
        "term_months": 2,
        "product_code": "overdraft_demo",
        "prefill_source": "recommendation",
    }
    created = world["as_preparer"].post("/api/applications", body, format="json")

    assert created.status_code == 201
    assert_matches_contract(created, method="post", path="/api/applications", request_body=body)
    data = created.json()
    assert data["status"] == "draft"
    assert data["version"] == 0
    assert data["product_code"] == "overdraft_demo"
    assert data["available_actions"] == ["edit", "upload_document"]  # preparer cannot submit

    listed = world["as_signatory"].get("/api/applications")
    assert_matches_contract(listed, method="get", path="/api/applications")
    assert [item["id"] for item in listed.json()] == [data["id"]]

    detail = world["as_signatory"].get(f"/api/applications/{data['id']}")
    assert_matches_contract(detail, method="get", path=f"/api/applications/{data['id']}")
    assert detail.json()["offer"] is None
    assert detail.json()["decision"] is None
    assert "submit" in detail.json()["available_actions"]


def test_create_with_unknown_product_is_400(world):
    body = {"need_type": "capex", "purpose": "Станок", "requested_amount": "1.00", "term_months": 3}
    response = world["as_signatory"].post(
        "/api/applications", {**body, "product_code": "nope"}, format="json"
    )
    assert response.status_code == 400
    assert "product_code" in response.json()["error"]["details"]


def test_autosave_with_version_and_conflict(world):
    application = make_application(world["company"])
    url = f"/api/applications/{application.pk}"

    first = world["as_preparer"].patch(url, {"version": 0, "purpose": "Новая цель"}, format="json")
    assert first.status_code == 200
    assert_matches_contract(first, method="patch", path=url)
    assert first.json()["version"] == 1

    stale = world["as_signatory"].patch(url, {"version": 0, "term_months": 6}, format="json")
    assert stale.status_code == 409
    assert stale.json()["error"]["code"] == "version_conflict"
    assert_matches_contract(stale, method="patch", path=url)


def test_edit_is_only_for_drafts(world):
    application = make_application(world["company"], status=S.SUBMITTED)
    response = world["as_signatory"].patch(
        f"/api/applications/{application.pk}", {"version": 0, "purpose": "x"}, format="json"
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "invalid_transition"


def test_status_and_version_cannot_be_written(world):
    application = make_application(world["company"])
    response = world["as_signatory"].patch(
        f"/api/applications/{application.pk}",
        {"version": 0, "purpose": "x", "status": "issued"},
        format="json",
    )
    assert response.status_code == 200
    application.refresh_from_db()
    assert application.status == S.DRAFT


# ───────────────────────── submit: roles and idempotency ─────────────────────────


def test_submit_requires_idempotency_key(world):
    application = make_application(world["company"])
    response = world["as_signatory"].post(f"/api/applications/{application.pk}/submit")
    assert response.status_code == 400


def test_submit_is_idempotent_by_key(world):
    application = make_application(world["company"])
    key = str(uuid.uuid4())

    first = submit(world["as_signatory"], application.pk, key)
    retry = submit(world["as_signatory"], application.pk, key)

    assert first.status_code == retry.status_code == 200
    assert first.json() == retry.json()
    assert first.json()["status"] == "submitted"
    assert_matches_contract(first, method="post", path=f"/api/applications/{application.pk}/submit")
    assert ApplicationEvent.objects.filter(application=application).count() == 1

    another_key = submit(world["as_signatory"], application.pk)
    assert another_key.status_code == 409
    assert another_key.json()["error"]["code"] == "invalid_transition"


def test_preparer_cannot_submit(world):
    application = make_application(world["company"])
    response = submit(world["as_preparer"], application.pk)
    assert response.status_code == 403
    application.refresh_from_db()
    assert application.status == S.DRAFT


# ───────────────────────── scoping: someone else's id is 404 ─────────────────────────


@pytest.mark.parametrize(
    ("method", "suffix", "body"),
    [
        ("get", "", None),
        ("patch", "", {"version": 0, "purpose": "x"}),
        ("post", "/submit", None),
        ("post", "/cancel", None),
        ("get", "/events", None),
        ("get", "/decision", None),
        ("post", "/offer/accept", None),
        ("post", "/offer/decline", None),
        ("post", "/signature", None),
        ("post", "/signature/confirm", {"code": "123456"}),
        ("post", "/info-requests/1/respond", {"message": "x"}),
    ],
)
@pytest.mark.parametrize("who", ["as_outsider", "as_bank"])
def test_foreign_user_gets_404(world, method, suffix, body, who):
    application = make_application(world["company"])
    url = f"/api/applications/{application.pk}{suffix}"
    response = getattr(world[who], method)(
        url, body, format="json", HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4())
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


def test_anonymous_gets_401(world):
    from rest_framework.test import APIClient

    response = APIClient().get("/api/applications")
    assert response.status_code == 401
    assert_matches_contract(response, method="get", path="/api/applications")


# ───────────────────────── scenarios ─────────────────────────


def test_scenario_1_offer_signing_and_disbursement(world):
    """Coffee shop: submit → auto offer → accept → sign with the on-screen code → issued."""
    client = world["as_signatory"]
    application = make_application(world["company"], product=world["overdraft"])
    pk = application.pk
    submit(client, pk)
    services.start_processing(pk)
    services.record_auto_decision(
        pk,
        outcome=DecisionOutcome.OFFER,
        grade="A",
        policy_version="test",
        reasons=[reason()],
        offer=offer_terms(world["overdraft"]),
    )

    detail = client.get(f"/api/applications/{pk}")
    assert detail.json()["status"] == "offer"
    assert detail.json()["offer"]["monthly_payment"] is None  # overdraft is revolving
    assert detail.json()["decision"]["is_preliminary"] is True
    assert_matches_contract(detail, method="get", path=f"/api/applications/{pk}")

    accepted = client.post(f"/api/applications/{pk}/offer/accept")
    assert accepted.json()["status"] == "signing"
    assert accepted.json()["offer"]["status"] == "accepted"

    challenge = client.post(f"/api/applications/{pk}/signature")
    assert_matches_contract(challenge, method="post", path=f"/api/applications/{pk}/signature")
    code = challenge.json()["code"]
    wrong = "000000" if code != "000000" else "111111"

    bad = client.post(f"/api/applications/{pk}/signature/confirm", {"code": wrong}, format="json")
    assert bad.status_code == 400
    assert Signature.objects.get(application_id=pk).attempts_left == 4  # the attempt is spent

    signed = client.post(f"/api/applications/{pk}/signature/confirm", {"code": code}, format="json")
    assert signed.status_code == 200
    assert signed.json()["status"] == "signed"

    services.mark_issued(pk, account_masked="40702…0001")
    timeline = client.get(f"/api/applications/{pk}/events")
    assert_matches_contract(timeline, method="get", path=f"/api/applications/{pk}/events")
    statuses = [event["to_status"] for event in timeline.json() if event["to_status"]]
    assert statuses == ["submitted", "processing", "offer", "signing", "signed", "issued"]
    # the preparer was told about every client-facing step the director did not do himself
    assert Notification.objects.filter(user=world["preparer"]).count() >= 4


def test_scenario_3_counteroffer_by_dscr(world):
    application = make_application(
        world["company"], product=world["loan"], requested_amount=Decimal("5300000.00")
    )
    submit(world["as_signatory"], application.pk)
    services.start_processing(application.pk)
    services.record_auto_decision(
        application.pk,
        outcome=DecisionOutcome.COUNTEROFFER,
        grade="B",
        policy_version="test",
        reasons=[reason(value="1.2500", passed=True)],
        offer=offer_terms(world["loan"], amount="2009314.00", rate="0.24"),
    )

    offer = world["as_signatory"].get(f"/api/applications/{application.pk}").json()["offer"]
    assert offer["is_counteroffer"] is True
    assert offer["product_changed"] is False
    assert offer["amount"] == "2009314.00"
    assert offer["requested_amount"] == "5300000.00"
    assert offer["monthly_payment"] is not None


def test_completeness_check_asks_and_reruns_the_pipeline(world):
    """F6: validation finds gaps → info_requested(origin=validation) → answer → submitted."""
    application = make_application(world["company"])
    submit(world["as_signatory"], application.pk)
    services.start_processing(application.pk)
    services.record_auto_decision(
        application.pk,
        outcome=DecisionOutcome.INFO_REQUESTED,
        grade=None,
        policy_version="test",
        reasons=[],
        info_request={"message": "Уточните цель", "fields": ["purpose"]},
    )
    request = InfoRequest.objects.get(application=application)
    assert request.origin == "validation"

    url = f"/api/applications/{application.pk}/info-requests/{request.pk}/respond"
    answered = world["as_preparer"].post(url, {"message": "Закупка к сезону"}, format="json")

    assert answered.status_code == 200
    assert_matches_contract(answered, method="post", path=url)
    assert answered.json()["status"] == "submitted"
    again = world["as_preparer"].post(url, {"message": "ещё раз"}, format="json")
    assert again.status_code == 404


def test_cancel_by_signatory_from_offer_declines_the_offer(world):
    application = make_application(world["company"], product=world["overdraft"])
    submit(world["as_signatory"], application.pk)
    services.start_processing(application.pk)
    services.record_auto_decision(
        application.pk,
        outcome=DecisionOutcome.OFFER,
        grade="A",
        policy_version="test",
        reasons=[],
        offer=offer_terms(world["overdraft"]),
    )
    response = world["as_signatory"].post(f"/api/applications/{application.pk}/offer/decline")
    assert response.json()["status"] == "cancelled"
    assert response.json()["offer"] is None


def test_decision_is_404_until_there_is_one(world):
    application = make_application(world["company"])
    response = world["as_signatory"].get(f"/api/applications/{application.pk}/decision")
    assert response.status_code == 404
    assert_matches_contract(
        response, method="get", path=f"/api/applications/{application.pk}/decision"
    )
