import uuid

from apps.documents.signatures import EXTENSIONS


def document_upload_to(instance: object, filename: str) -> str:
    """Random storage name. `filename` is the client name and is ignored on purpose."""
    content_type = getattr(instance, "content_type", "")
    extension = EXTENSIONS[content_type]
    return f"documents/{uuid.uuid4().hex}.{extension}"
