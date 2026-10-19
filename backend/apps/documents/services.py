import hashlib

from django.conf import settings
from django.core.files.uploadedfile import UploadedFile
from django.db import transaction
from rest_framework.exceptions import NotFound, ValidationError

from apps.applications.models import Application, ApplicationStatus
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
    application = Application.objects.filter(pk=application_id, business__owner=user).first()
    if application is None:
        raise NotFound(_NOT_FOUND)
    return application


def get_owned_document(user: object, application_id: int, document_id: int) -> Document:
    document = (
        Document.objects.filter(
            pk=document_id,
            application_id=application_id,
            application__business__owner=user,
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
            .filter(pk=application_id, business__owner=user)
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

        document = Document(
            application=application,
            kind=kind,
            original_name=safe_original_name(upload.name),
            content_type=content_type,
            size=size,
            sha256=_sha256(upload),
        )
        document.file = upload
        document.save()
        return document


def _sha256(upload: UploadedFile) -> str:
    digest = hashlib.sha256()
    for chunk in upload.chunks():
        digest.update(chunk)
    upload.seek(0)
    return digest.hexdigest()
