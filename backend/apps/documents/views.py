from django.http import FileResponse
from rest_framework.parsers import MultiPartParser
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.documents.names import attachment_filename
from apps.documents.serializers import DocumentSerializer, DocumentUploadSerializer
from apps.documents.services import (
    get_owned_application,
    get_owned_document,
    list_documents,
    store_document,
)


class ApplicationDocumentListView(APIView):
    """GET/POST /api/applications/{id}/documents (openapi: list and upload)."""

    parser_classes = (MultiPartParser,)

    def get(self, request: Request, application_id: int) -> Response:
        documents = list_documents(request.user, application_id)
        body = DocumentSerializer(documents, many=True, context={"request": request})
        return Response(body.data)

    def post(self, request: Request, application_id: int) -> Response:
        # Ownership before body validation: a foreign id is 404, not 400.
        get_owned_application(request.user, application_id)
        serializer = DocumentUploadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        document = store_document(
            user=request.user,
            application_id=application_id,
            kind=serializer.validated_data["kind"],
            upload=serializer.validated_data["file"],
        )
        body = DocumentSerializer(document, context={"request": request})
        return Response(body.data, status=201)


class ApplicationDocumentDownloadView(APIView):
    """File bytes for Document.download_url. Always an attachment.

    The path is not in docs/openapi.yaml yet (the schema only has download_url).
    """

    def get(self, request: Request, application_id: int, document_id: int) -> FileResponse:
        document = get_owned_document(request.user, application_id, document_id)
        response = FileResponse(
            document.file.open("rb"),
            as_attachment=True,
            filename=attachment_filename(document.original_name, document.content_type),
            content_type=document.content_type,
        )
        response["X-Content-Type-Options"] = "nosniff"
        return response
