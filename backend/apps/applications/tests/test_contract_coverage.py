"""Fix 2.2: contract tests for the operations no other test checked against docs/openapi.yaml.

Officer decisions, cancel, offer decline, signature confirm, document download, notifications
and logout. Each answer — success and the usual error — is validated by assert_matches_contract,
so a change of shape fails CI instead of the frontend.
"""

from decimal import Decimal
from types import SimpleNamespace

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from apps.applications import services
from apps.applications.models import ApplicationStatus, DecisionOutcome
from apps.core.factories import make_application
from apps.core.testing import assert_matches_contract
from apps.notifications.models import Notification

pytestmark = pytest.mark.django_db
S = ApplicationStatus
PDF = b"%PDF-1.4\n1 0 obj\n<<>>\ntrailer\n%%EOF"


@pytest.fixture
def media(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path


def _offer(world, status: str = S.OFFER):
    """An application with an active automatic offer (or moved on to `status`)."""
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
    application.refresh_from_db()
    return application


def _check(response, method: str, path: str, body=None) -> None:
    assert_matches_contract(response, method=method, path=path, request_body=body)


# ───────────────────────── client: cancel, offer decline, signature ─────────────────────────


def test_cancel(world):
    application = make_application(world["company"])
    path = f"/api/applications/{application.pk}/cancel"
    done = world["as_signatory"].post(path)
    assert done.status_code == 200
    _check(done, "post", path)
    again = world["as_signatory"].post(path)  # already cancelled
    assert again.status_code == 409
    _check(again, "post", path)
    assert world["as_preparer"].post(path).status_code == 403


def test_offer_decline(world):
    application = _offer(world)
    path = f"/api/applications/{application.pk}/offer/decline"
    forbidden = world["as_preparer"].post(path)
    assert forbidden.status_code == 403
    _check(forbidden, "post", path)
    done = world["as_signatory"].post(path)
    assert done.status_code == 200
    assert done.json()["status"] == "cancelled"
    _check(done, "post", path)
    assert world["as_outsider"].post(path).status_code == 404


def test_signature_confirm(world):
    application = _offer(world)
    pk = application.pk
    world["as_signatory"].post(f"/api/applications/{pk}/offer/accept")
    code = world["as_signatory"].post(f"/api/applications/{pk}/signature").json()["code"]
    path = f"/api/applications/{pk}/signature/confirm"

    wrong = {"code": "000000" if code != "000000" else "111111"}
    bad = world["as_signatory"].post(path, wrong, format="json")
    assert bad.status_code == 400
    _check(bad, "post", path, wrong)

    signed = world["as_signatory"].post(path, {"code": code}, format="json")
    assert signed.status_code == 200
    assert signed.json()["status"] == "signed"
    _check(signed, "post", path, {"code": code})


# ───────────────────────── client: document download ─────────────────────────


def _read(response):
    """FileResponse streams: give the contract check its body in one piece. openapi-core wants a
    str for `type: string, format: binary`, so the bytes go as latin-1 — one char per byte."""
    return SimpleNamespace(
        status_code=response.status_code,
        content=b"".join(response.streaming_content).decode("latin-1"),
        get=response.get,
    )


def test_document_download(world, media):
    application = make_application(world["company"])
    upload = SimpleUploadedFile("выписка.pdf", PDF, content_type="application/pdf")
    created = world["as_preparer"].post(
        f"/api/applications/{application.pk}/documents",
        {"kind": "bank_statement", "file": upload},
        format="multipart",
    )
    path = f"/api/applications/{application.pk}/documents/{created.json()['id']}"

    response = world["as_signatory"].get(path)
    assert response.status_code == 200
    assert response["Content-Type"] == "application/pdf"
    assert response["Content-Disposition"].startswith("attachment")
    _check(_read(response), "get", path)

    missing = world["as_outsider"].get(path)
    assert missing.status_code == 404
    _check(missing, "get", path)


# ───────────────────────── notifications ─────────────────────────


def _note(user, application=None) -> Notification:
    return Notification.objects.create(
        user=user, application=application, kind="decision", title="Готово предложение"
    )


def test_mark_notification_read(world):
    note = _note(world["signatory"])
    path = f"/api/notifications/{note.pk}/read"
    done = world["as_signatory"].post(path)
    assert done.status_code == 204
    _check(done, "post", path)
    note.refresh_from_db()
    assert note.read_at is not None

    foreign = world["as_outsider"].post(path)  # someone else's notification
    assert foreign.status_code == 404
    _check(foreign, "post", path)


def test_mark_all_notifications_read(world):
    _note(world["signatory"])
    _note(world["signatory"])
    mine_only = _note(world["preparer"])
    done = world["as_signatory"].post("/api/notifications/read-all")
    assert done.status_code == 204
    _check(done, "post", "/api/notifications/read-all")
    assert not Notification.objects.filter(user=world["signatory"], read_at=None).exists()
    mine_only.refresh_from_db()
    assert mine_only.read_at is None  # another user's stay unread


# ───────────────────────── logout ─────────────────────────


def test_logout(world):
    done = world["as_signatory"].post("/api/auth/logout")
    assert done.status_code == 204
    _check(done, "post", "/api/auth/logout")
    assert world["as_signatory"].get("/api/auth/me").status_code == 401


# ───────────────────────── officer decisions ─────────────────────────


def _bank(pk: int, suffix: str) -> str:
    return f"/api/bank/applications/{pk}{suffix}"


@pytest.mark.parametrize(
    ("suffix", "body", "status"),
    [
        ("/approve", {"version": 0}, "offer"),
        (
            "/counteroffer",
            {
                "version": 0,
                "amount": "300000.00",
                "term_months": 12,
                "rate": "0.24",
                "comment": "Поток выдерживает меньшую сумму",
            },
            "offer",
        ),
        (
            "/request-info",
            {"version": 0, "message": "Загрузите договор поставки", "document_kinds": ["contract"]},
            "info_requested",
        ),
        (
            "/decline",
            {
                "version": 0,
                "reasons_text": "80% выручки от одного покупателя",
                "improvements": ["Снизить зависимость от одного покупателя"],
            },
            "declined",
        ),
    ],
)
def test_officer_decisions(world, suffix, body, status):
    application = make_application(
        world["company"],
        status=S.MANUAL_REVIEW,
        product=world["loan"],
        requested_amount=Decimal("500000.00"),  # the counteroffer gives less, within the product
    )
    path = _bank(application.pk, suffix)

    done = world["as_bank"].post(path, body, format="json")
    assert done.status_code == 200, done.json()
    assert done.json()["application"]["status"] == status
    _check(done, "post", path, body)

    stale = world["as_bank"].post(path, body, format="json")  # version 0 is gone
    assert stale.status_code == 409
    _check(stale, "post", path, body)

    client = world["as_signatory"].post(path, body, format="json")
    assert client.status_code == 403
    _check(client, "post", path, body)
