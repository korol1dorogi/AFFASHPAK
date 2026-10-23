"""Bank workplace API: card, officer actions, optimistic locking, internal comments."""

import uuid

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from apps.applications.models import ApplicationStatus, Decision, Score
from apps.core.factories import make_application
from apps.core.testing import assert_matches_contract
from apps.documents.tests.test_signatures import PDF_BYTES

S = ApplicationStatus


def bank_url(pk: int, suffix: str = "") -> str:
    return f"/api/bank/applications/{pk}{suffix}"


@pytest.fixture
def media(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    return tmp_path


@pytest.mark.parametrize(
    ("method", "suffix"),
    [
        ("get", ""),
        ("post", "/assign"),
        ("post", "/approve"),
        ("post", "/counteroffer"),
        ("post", "/request-info"),
        ("post", "/decline"),
        ("post", "/comments"),
    ],
)
def test_clients_get_403_on_bank_endpoints(world, method, suffix):
    application = make_application(world["company"], status=S.MANUAL_REVIEW)
    response = getattr(world["as_signatory"], method)(
        bank_url(application.pk, suffix), {}, format="json"
    )
    assert response.status_code == 403


def test_unknown_application_is_404_for_the_bank(world):
    response = world["as_bank"].get(bank_url(999999))
    assert response.status_code == 404


def test_scored_card_matches_contract(world):
    """Factor values are numeric strings or null, as apps/scoring stores them (ScoreFactor)."""
    application = make_application(world["company"], status=S.MANUAL_REVIEW, product=world["loan"])
    Score.objects.create(
        application=application,
        grade="C",
        total=65,
        model_version="scorecard-2026.10-v1",
        factors=[
            {"name": "business_age_months", "value": "36", "points": 10, "message": "Демо"},
            {"name": "dscr", "value": "1.8000", "points": 18, "message": "Демо"},
            {"name": "debt_to_ebitda", "value": None, "points": 7, "message": "Демо"},
        ],
    )
    response = world["as_bank"].get(bank_url(application.pk))

    assert response.status_code == 200
    assert_matches_contract(response, method="get", path=bank_url(application.pk))
    assert [f["value"] for f in response.json()["score"]["factors"]] == ["36", "1.8000", None]


def test_card_matches_contract(world):
    application = make_application(world["company"], status=S.MANUAL_REVIEW, product=world["loan"])
    response = world["as_bank"].get(bank_url(application.pk))

    assert response.status_code == 200
    assert_matches_contract(response, method="get", path=bank_url(application.pk))
    body = response.json()
    assert body["company"]["my_role"] is None
    assert [m["role"] for m in body["members"]] == ["signatory", "preparer"]
    assert body["application"]["available_actions"] == [
        "assign",
        "approve",
        "counteroffer",
        "request_info",
        "decline",
    ]


def test_assign_and_stale_version(world):
    application = make_application(world["company"], status=S.MANUAL_REVIEW)
    url = bank_url(application.pk, "/assign")

    assigned = world["as_bank"].post(url, {"version": 0}, format="json")
    assert assigned.status_code == 200
    assert_matches_contract(assigned, method="post", path=url, request_body={"version": 0})
    assert assigned.json()["assignee"]["full_name"] == "Менеджер (демо)"
    assert assigned.json()["application"]["version"] == 1

    stale = world["as_bank"].post(
        bank_url(application.pk, "/approve"), {"version": 0}, format="json"
    )
    assert stale.status_code == 409
    assert stale.json()["error"]["code"] == "version_conflict"


def test_approve_creates_offer_on_requested_terms(world):
    application = make_application(world["company"], status=S.MANUAL_REVIEW, product=world["loan"])
    response = world["as_bank"].post(
        bank_url(application.pk, "/approve"), {"version": 0}, format="json"
    )

    assert response.status_code == 200
    body = response.json()
    assert body["application"]["status"] == "offer"
    assert body["offer"]["is_counteroffer"] is False
    assert body["offer"]["amount"] == "100000.00"
    assert body["decisions"][-1]["decided_by"] == "officer"
    assert body["decisions"][-1]["is_preliminary"] is False


def test_approve_without_product_is_400(world):
    application = make_application(world["company"], status=S.MANUAL_REVIEW, product=None)
    response = world["as_bank"].post(
        bank_url(application.pk, "/approve"), {"version": 0}, format="json"
    )
    assert response.status_code == 400


def test_counteroffer_with_another_product_is_alternative_product(world):
    application = make_application(world["company"], status=S.MANUAL_REVIEW, product=world["loan"])
    body = {
        "version": 0,
        "product_code": "overdraft_demo",
        "amount": "600000.00",
        "term_months": 6,
        "rate": "0.22",
        "comment": "Под вашу задачу лучше подойдёт овердрафт",
    }
    response = world["as_bank"].post(bank_url(application.pk, "/counteroffer"), body, format="json")

    assert response.status_code == 200
    offer = response.json()["offer"]
    assert offer["product_changed"] is True
    assert offer["product"]["code"] == "overdraft_demo"
    assert Decision.objects.get(application=application).outcome == "alternative_product"


def test_decline_requires_improvements_and_reaches_the_client(world):
    application = make_application(world["company"], status=S.MANUAL_REVIEW)
    url = bank_url(application.pk, "/decline")

    empty = world["as_bank"].post(
        url, {"version": 0, "reasons_text": "x", "improvements": []}, format="json"
    )
    assert empty.status_code == 400

    body = {
        "version": 0,
        "reasons_text": "80% выручки от одного покупателя",
        "improvements": ["Снизить зависимость от одного покупателя"],
    }
    declined = world["as_bank"].post(url, body, format="json")
    assert declined.json()["application"]["status"] == "declined"

    decision = world["as_signatory"].get(f"/api/applications/{application.pk}/decision").json()
    assert decision["outcome"] == "declined"
    assert decision["improvements"] == ["Снизить зависимость от одного покупателя"]


def test_scenario_4_info_request_document_and_approval(world, media):
    """Manual review → bank asks for a document → client uploads and answers → approval."""
    application = make_application(world["company"], status=S.MANUAL_REVIEW, product=world["loan"])
    pk = application.pk

    asked = world["as_bank"].post(
        bank_url(pk, "/request-info"),
        {"version": 0, "message": "Загрузите договор на станок", "document_kinds": ["contract"]},
        format="json",
    )
    assert asked.json()["application"]["status"] == "info_requested"

    detail = world["as_preparer"].get(f"/api/applications/{pk}").json()
    (request,) = detail["open_info_requests"]
    assert request["origin"] == "officer"
    assert "upload_document" in detail["available_actions"]

    upload = SimpleUploadedFile("договор.pdf", PDF_BYTES, content_type="application/pdf")
    uploaded = world["as_preparer"].post(
        f"/api/applications/{pk}/documents",
        {"kind": "contract", "file": upload},
        format="multipart",
    )
    assert uploaded.status_code == 201

    answered = world["as_preparer"].post(
        f"/api/applications/{pk}/info-requests/{request['id']}/respond",
        {"message": "Договор загрузила"},
        format="json",
    )
    assert answered.json()["status"] == "manual_review"

    card = world["as_bank"].get(bank_url(pk)).json()
    (document,) = card["documents"]
    assert document["download_url"].endswith(bank_url(pk, f"/documents/{document['id']}"))
    assert world["as_bank"].get(document["download_url"]).status_code == 200

    approved = world["as_bank"].post(
        bank_url(pk, "/approve"), {"version": card["application"]["version"]}, format="json"
    )
    assert approved.json()["application"]["status"] == "offer"
    kinds = [event["kind"] for event in card["events"]]
    assert "document_uploaded" in kinds
    assert "info_responded" in kinds


def test_internal_comment_is_hidden_from_the_client(world):
    application = make_application(world["company"], status=S.MANUAL_REVIEW)
    url = bank_url(application.pk, "/comments")
    created = world["as_bank"].post(url, {"message": "Проверить залог"}, format="json")

    assert created.status_code == 201
    assert_matches_contract(created, method="post", path=url, request_body={"message": "x"})
    assert created.json()["is_internal"] is True
    timeline = world["as_signatory"].get(f"/api/applications/{application.pk}/events").json()
    assert all(event["message"] != "Проверить залог" for event in timeline)


def test_clients_cannot_download_through_the_bank_route(world, media):
    application = make_application(world["company"])
    upload = SimpleUploadedFile("выписка.pdf", PDF_BYTES, content_type="application/pdf")
    document = (
        world["as_signatory"]
        .post(
            f"/api/applications/{application.pk}/documents",
            {"kind": "bank_statement", "file": upload},
            format="multipart",
            HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4()),
        )
        .json()
    )
    path = bank_url(application.pk, f"/documents/{document['id']}")
    response = world["as_signatory"].get(path)
    assert response.status_code == 403  # like the rest of /api/bank/*, before any lookup
    assert_matches_contract(response, method="get", path=path)
