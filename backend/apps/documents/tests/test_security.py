import hashlib
import re
from datetime import date
from decimal import Decimal

import pytest
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APIClient

from apps.applications.models import Application, ApplicationStatus
from apps.business.models import Business, LegalForm
from apps.core.testing import assert_matches_contract
from apps.documents.models import Document
from apps.documents.services import store_document
from apps.documents.tests.test_signatures import JPEG_BYTES, PDF_BYTES, PNG_BYTES

_STORAGE_NAME = re.compile(r"documents/[0-9a-f]{32}\.(pdf|png|jpg)\Z")


@pytest.fixture
def media(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    return tmp_path


def _user(username: str) -> User:
    return User.objects.create_user(username, password="demo-password")


def _application(owner: User, status: str = ApplicationStatus.DRAFT) -> Application:
    business = Business.objects.create(
        owner=owner,
        legal_form=LegalForm.OOO,
        name="ООО Ромашка (демо)",
        inn="0000000000",
        ogrn="0000000000000",
        okved="56.10",
        registered_at=date(2020, 1, 15),
        region="00",
        is_demo=True,
    )
    return Application.objects.create(
        business=business,
        need_type="cash_gap",
        purpose="Демо: кассовый разрыв",
        requested_amount=Decimal("100000.00"),
        term_months=12,
        status=status,
        prefill_source="manual",
    )


def _client(user: User) -> APIClient:
    client = APIClient()
    client.force_login(user)
    return client


def _file(
    name: str,
    payload: bytes,
    content_type: str = "application/octet-stream",
) -> SimpleUploadedFile:
    return SimpleUploadedFile(name, payload, content_type=content_type)


def _url(application_id: int) -> str:
    return f"/api/applications/{application_id}/documents"


def _download_url(application_id: int, document_id: int) -> str:
    return f"/api/applications/{application_id}/documents/{document_id}"


def _upload(
    client: APIClient,
    application_id: int,
    upload: SimpleUploadedFile,
    kind: str = "bank_statement",
):
    return client.post(_url(application_id), {"kind": kind, "file": upload}, format="multipart")


@pytest.mark.django_db
def test_upload_list_and_download_match_contract(media):
    owner = _user("demo-owner")
    application = _application(owner)
    client = _client(owner)

    created = _upload(client, application.id, _file("выписка.pdf", PDF_BYTES, "text/html"))

    assert created.status_code == 201
    body = created.json()
    assert body["kind"] == "bank_statement"
    assert body["filename"] == "выписка.pdf"
    assert body["content_type"] == "application/pdf"
    assert body["size"] == len(PDF_BYTES)
    assert body["sha256"] == hashlib.sha256(PDF_BYTES).hexdigest()
    assert body["download_url"].endswith(_download_url(application.id, body["id"]))
    assert_matches_contract(created, method="post", path=_url(application.id))

    stored = Document.objects.get(pk=body["id"])
    assert _STORAGE_NAME.fullmatch(stored.file.name)
    assert stored.file.name not in created.content.decode()
    assert "выписка" not in stored.file.name
    assert stored.file.read() == PDF_BYTES

    listed = client.get(_url(application.id))
    assert listed.status_code == 200
    assert [item["id"] for item in listed.json()] == [body["id"]]
    assert_matches_contract(listed, method="get", path=_url(application.id))

    downloaded = client.get(body["download_url"])
    assert downloaded.status_code == 200
    assert downloaded["Content-Type"].split(";")[0] == "application/pdf"
    assert downloaded["Content-Disposition"].startswith("attachment;")
    assert "filename" in downloaded["Content-Disposition"]
    assert downloaded["X-Content-Type-Options"] == "nosniff"
    assert "\r" not in downloaded["Content-Disposition"]
    assert "\n" not in downloaded["Content-Disposition"]
    assert b"".join(downloaded.streaming_content) == PDF_BYTES

    media_response = client.get(f"/media/{stored.file.name}")
    assert media_response.status_code == 404


@pytest.mark.django_db
def test_png_and_jpeg_are_served_as_their_own_types(media):
    owner = _user("demo-owner")
    application = _application(owner)
    client = _client(owner)

    png = _upload(
        client,
        application.id,
        _file("scan.pdf", PNG_BYTES, "application/pdf"),
        kind="invoice",
    )
    jpeg = _upload(client, application.id, _file("photo.png", JPEG_BYTES), kind="other")

    assert png.status_code == 201
    assert jpeg.status_code == 201
    assert png.json()["content_type"] == "image/png"
    assert jpeg.json()["content_type"] == "image/jpeg"
    assert Document.objects.get(pk=png.json()["id"]).file.name.endswith(".png")
    assert Document.objects.get(pk=jpeg.json()["id"]).file.name.endswith(".jpg")

    png_file = client.get(_download_url(application.id, png.json()["id"]))
    assert png_file["Content-Type"].split(";")[0] == "image/png"
    disposition = png_file["Content-Disposition"]
    assert "scan.png" in disposition


@pytest.mark.django_db
def test_anonymous_and_foreign_user_get_401_and_404(media):
    owner = _user("demo-owner")
    stranger = _user("demo-stranger")
    application = _application(owner)
    other = _application(stranger, status=ApplicationStatus.SUBMITTED)
    owner_client = _client(owner)
    created = _upload(owner_client, application.id, _file("statement.pdf", PDF_BYTES))
    document_id = created.json()["id"]

    anonymous = APIClient()
    anonymous_list = anonymous.get(_url(application.id))
    assert anonymous_list.status_code == 401
    assert anonymous_list.json()["error"]["code"] == "not_authenticated"
    assert_matches_contract(anonymous_list, method="get", path=_url(application.id))
    assert anonymous.post(_url(application.id), {}, format="multipart").status_code == 401
    assert anonymous.get(_download_url(application.id, document_id)).status_code == 401

    missing = owner_client.get(_url(999_999))
    foreign_list = owner_client.get(_url(other.id))
    assert missing.status_code == foreign_list.status_code == 404
    assert missing.json() == foreign_list.json()

    foreign_upload = owner_client.post(_url(other.id), {}, format="multipart")
    assert foreign_upload.status_code == 404
    assert foreign_upload.json()["error"]["code"] == "not_found"

    foreign_download = owner_client.get(_download_url(other.id, document_id))
    swapped = owner_client.get(_download_url(application.id, document_id + 99))
    assert foreign_download.status_code == swapped.status_code == 404
    assert Document.objects.count() == 1


@pytest.mark.django_db
def test_post_without_csrf_is_forbidden(media):
    owner = _user("demo-owner")
    application = _application(owner)
    client = APIClient(enforce_csrf_checks=True)
    client.force_login(owner)

    response = client.post(
        _url(application.id),
        {"kind": "bank_statement", "file": _file("statement.pdf", PDF_BYTES)},
        format="multipart",
    )

    assert response.status_code == 403
    assert Document.objects.count() == 0


@pytest.mark.django_db
@pytest.mark.parametrize(
    "payload",
    [
        b"<html><script>alert(1)</script></html>",
        b"<svg xmlns='http://www.w3.org/2000/svg'></svg>",
        b"MZ" + b"\x00" * 16,
        b"PK\x03\x04" + b"\x00" * 16,
        b"\n%PDF-1.4\n",
    ],
)
def test_disallowed_signature_is_rejected_and_not_stored(media, payload: bytes):
    owner = _user("demo-owner")
    application = _application(owner)
    client = _client(owner)

    response = _upload(client, application.id, _file("statement.pdf", payload, "application/pdf"))

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid"
    assert Document.objects.count() == 0
    assert list(media.rglob("*")) == []


@pytest.mark.django_db
def test_path_and_header_injection_do_not_change_storage_or_disposition(media):
    owner = _user("demo-owner")
    application = _application(owner)
    client = _client(owner)

    created = _upload(client, application.id, _file("../../secret.pdf", PDF_BYTES, "text/html"))

    assert created.status_code == 201
    assert created.json()["filename"] == "secret.pdf"
    stored = Document.objects.get()
    assert _STORAGE_NAME.fullmatch(stored.file.name)
    assert "secret" not in stored.file.name
    downloaded = client.get(_download_url(application.id, stored.id))
    disposition = downloaded["Content-Disposition"]
    assert disposition.startswith("attachment;")
    assert "\r" not in disposition
    assert "\n" not in disposition
    assert "X-Injected" not in downloaded


@pytest.mark.django_db
@pytest.mark.django_db
def test_control_characters_never_reach_the_download_header(media):
    owner = _user("demo-owner")
    application = _application(owner)
    upload = SimpleUploadedFile("evil.pdf\r\nX-Injected: 1", PDF_BYTES)

    document = store_document(
        user=owner,
        application_id=application.id,
        kind="other",
        upload=upload,
    )

    assert "\r" not in document.original_name
    assert "\n" not in document.original_name
    downloaded = _client(owner).get(_download_url(application.id, document.id))
    assert "\r" not in downloaded["Content-Disposition"]
    assert "\n" not in downloaded["Content-Disposition"]
    assert "X-Injected" not in downloaded


@pytest.mark.django_db
def test_empty_file_and_unknown_kind_are_400(media):
    owner = _user("demo-owner")
    application = _application(owner)
    client = _client(owner)

    empty = _upload(client, application.id, _file("statement.pdf", b""))
    unknown = _upload(client, application.id, _file("statement.pdf", PDF_BYTES), kind="passport")

    assert empty.status_code == 400
    assert unknown.status_code == 400
    assert Document.objects.count() == 0


@pytest.mark.django_db
def test_file_over_the_app_limit_is_413_and_not_stored(media, settings):
    settings.UPLOAD_MAX_FILE_BYTES = len(PDF_BYTES) - 1
    owner = _user("demo-owner")
    application = _application(owner)

    response = _upload(_client(owner), application.id, _file("statement.pdf", PDF_BYTES))

    assert response.status_code == 413
    assert response.json()["error"]["code"] == "payload_too_large"
    assert Document.objects.count() == 0
    assert list(media.rglob("*")) == []


@pytest.mark.django_db
def test_file_at_the_app_limit_is_stored(media, settings):
    settings.UPLOAD_MAX_FILE_BYTES = len(PDF_BYTES)
    owner = _user("demo-owner")
    application = _application(owner)

    response = _upload(_client(owner), application.id, _file("statement.pdf", PDF_BYTES))

    assert response.status_code == 201
    assert Document.objects.count() == 1


@pytest.mark.django_db
@pytest.mark.parametrize(
    "status",
    [
        ApplicationStatus.SUBMITTED,
        ApplicationStatus.IN_REVIEW,
        ApplicationStatus.APPROVED,
        ApplicationStatus.DECLINED,
        ApplicationStatus.CANCELLED,
    ],
)
def test_upload_outside_draft_and_info_requested_is_409(media, status: str):
    owner = _user("demo-owner")
    application = _application(owner, status=status)

    response = _upload(_client(owner), application.id, _file("statement.pdf", PDF_BYTES))

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "invalid_transition"
    assert Document.objects.count() == 0


@pytest.mark.django_db
def test_upload_is_allowed_when_the_bank_asked_for_documents(media):
    owner = _user("demo-owner")
    application = _application(owner, status=ApplicationStatus.INFO_REQUESTED)

    response = _upload(
        _client(owner),
        application.id,
        _file("statement.pdf", PDF_BYTES),
        kind="contract",
    )

    assert response.status_code == 201
    assert response.json()["kind"] == "contract"


@pytest.mark.django_db
def test_list_is_empty_for_a_new_application_and_hides_other_owners(media):
    owner = _user("demo-owner")
    stranger = _user("demo-stranger")
    application = _application(owner)
    other = _application(stranger)
    _upload(_client(stranger), other.id, _file("statement.pdf", PDF_BYTES))

    response = _client(owner).get(_url(application.id))

    assert response.status_code == 200
    assert response.json() == []
    assert_matches_contract(response, method="get", path=_url(application.id))
