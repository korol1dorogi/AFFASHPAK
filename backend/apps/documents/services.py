import hashlib

from django.conf import settings
from django.core.files.uploadedfile import UploadedFile
from django.db import transaction
from rest_framework.exceptions import NotFound, ValidationError

from apps.applications.access import Actor, client_applications, is_bank_user
from apps.applications.models import (
    Application,
    ApplicationStatus,
    EventKind,
    InfoRequestStatus,
)
from apps.applications.transitions import record_event
from apps.documents.exceptions import Conflict, PayloadTooLarge
from apps.documents.models import Document
from apps.documents.names import safe_original_name
from apps.documents.signatures import detect_content_type

_HEADER_BYTES = 16
_NOT_FOUND = "Не найдено."

UPLOADABLE_STATUSES = frozenset(
    {
        ApplicationStatus.DRAFT,
        ApplicationStatus.INFO_REQUESTED,
    }
)


def get_owned_application(user: object, application_id: int) -> Application:
    """Application of a company the user is a member of (client scoping, docs/data-model.md)."""
    application = client_applications(user).filter(pk=application_id).first()
    if application is None:
        raise NotFound(_NOT_FOUND)
    return application


def get_owned_document(user: object, application_id: int, document_id: int) -> Document:
    document = (
        Document.objects.filter(
            pk=document_id,
            application_id=application_id,
            application__in=client_applications(user),
        )
        .select_related("application")
        .first()
    )
    stored = document.file.name if document is not None and document.file else ""
    if document is None or not stored or not document.file.storage.exists(stored):
        raise NotFound(_NOT_FOUND)
    return document


def list_documents(user: object, application_id: int) -> list[Document]:
    application = get_owned_application(user, application_id)
    return list(application.documents.all())


def store_document(
    *,
    user: object,
    application_id: int,
    kind: str,
    upload: UploadedFile,
) -> Document:
    with transaction.atomic():
        application = (
            Application.objects.select_for_update()
            .filter(pk=application_id, company__memberships__user=user)
            .first()
        )
        if application is None:
            raise NotFound(_NOT_FOUND)
        if application.status not in UPLOADABLE_STATUSES:
            raise Conflict()

        size = upload.size or 0
        if size < 1:
            raise ValidationError({"file": ["Загрузите непустой файл."]})
        if size > settings.UPLOAD_MAX_FILE_BYTES:
            raise PayloadTooLarge()

        header = upload.read(_HEADER_BYTES)
        upload.seek(0)
        content_type = detect_content_type(header)
        if content_type is None:
            raise ValidationError(
                {"file": ["Тип файла не поддерживается. Загрузите PDF, JPEG или PNG."]}
            )

        open_request = application.info_requests.filter(status=InfoRequestStatus.OPEN).last()
        document = Document(
            application=application,
            uploaded_by=user,
            info_request=open_request,
            kind=kind,
            original_name=safe_original_name(upload.name),
            content_type=content_type,
            size=size,
            sha256=_sha256(upload),
        )
        document.file = upload
        document.save()
        record_event(
            application,
            Actor(kind="client", user=user),
            EventKind.DOCUMENT_UPLOADED,
            f"Загружен документ: {document.original_name}",
            payload={"document_id": document.pk, "kind": kind},
        )
        return document


def get_bank_document(user: object, application_id: int, document_id: int) -> Document:
    """Any application's document for a bank user; existence-only 404 otherwise."""
    if not is_bank_user(user):
        raise NotFound(_NOT_FOUND)
    document = Document.objects.filter(pk=document_id, application_id=application_id).first()
    stored = document.file.name if document is not None and document.file else ""
    if document is None or not stored or not document.file.storage.exists(stored):
        raise NotFound(_NOT_FOUND)
    return document


def _sha256(upload: UploadedFile) -> str:
    digest = hashlib.sha256()
    for chunk in upload.chunks():
        digest.update(chunk)
    upload.seek(0)
    return digest.hexdigest()
