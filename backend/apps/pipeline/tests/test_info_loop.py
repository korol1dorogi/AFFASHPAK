"""state-machine.md 10a: an answer to the completeness check runs the pipeline again."""

import uuid

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APIClient

from apps.documents.tests.test_signatures import PDF_BYTES


@pytest.fixture
def garden(seeded, settings):
    settings.DEMO_MODE = True
    client = APIClient()
    client.post("/api/demo/login", {"persona": "garden_store"}, format="json")
    return client


def submit(client, capture, body):
    app_id = client.post("/api/applications", body, format="json").json()["id"]
    with capture(execute=True):
        client.post(f"/api/applications/{app_id}/submit", HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4()))
    return app_id


BODY = {
    "need_type": "working_capital",
    "purpose": "Демо: закупка рассады к сезону",
    "requested_amount": "5300000.00",
    "term_months": 12,
    "product_code": "working_capital_loan_basic",
}


@pytest.mark.django_db
def test_missing_documents_asked_uploaded_answered_then_decided(
    garden, django_capture_on_commit_callbacks
):
    app_id = submit(garden, django_capture_on_commit_callbacks, BODY)
    detail = garden.get(f"/api/applications/{app_id}").json()
    assert detail["status"] == "info_requested"
    request = detail["open_info_requests"][0]
    assert set(request["document_kinds"]) == {"bank_statement", "tax_return"}

    for kind in request["document_kinds"]:
        upload = SimpleUploadedFile(f"{kind}.pdf", PDF_BYTES, "application/pdf")
        response = garden.post(
            f"/api/applications/{app_id}/documents",
            {"kind": kind, "file": upload},
            format="multipart",
        )
        assert response.status_code == 201
    with django_capture_on_commit_callbacks(execute=True):
        response = garden.post(
            f"/api/applications/{app_id}/info-requests/{request['id']}/respond",
            {"message": "Загрузили выписку и декларацию (демо)"},
            format="json",
        )
    assert response.status_code == 200

    detail = garden.get(f"/api/applications/{app_id}").json()
    assert detail["status"] == "offer"  # was: stuck in «submitted»
    assert detail["decision"]["outcome"] == "counteroffer"
    assert detail["offer"]["amount"] == "2009314.00"


@pytest.mark.django_db
def test_an_answer_without_the_documents_asks_again(garden, django_capture_on_commit_callbacks):
    app_id = submit(garden, django_capture_on_commit_callbacks, BODY)
    request = garden.get(f"/api/applications/{app_id}").json()["open_info_requests"][0]
    with django_capture_on_commit_callbacks(execute=True):
        garden.post(
            f"/api/applications/{app_id}/info-requests/{request['id']}/respond",
            {"message": "Документов нет"},
            format="json",
        )
    detail = garden.get(f"/api/applications/{app_id}").json()
    assert detail["status"] == "info_requested"
    assert len(detail["open_info_requests"]) == 1
