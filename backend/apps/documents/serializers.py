from django.urls import reverse
from rest_framework import serializers

from apps.documents.models import Document, DocumentKind


class DocumentUploadSerializer(serializers.Serializer):
    kind = serializers.ChoiceField(
        choices=DocumentKind.choices,
        error_messages={
            "required": "Укажите тип документа.",
            "invalid_choice": "Неизвестный тип документа.",
        },
    )
    file = serializers.FileField(
        allow_empty_file=False,
        error_messages={
            "required": "Загрузите файл.",
            "empty": "Загрузите непустой файл.",
            "invalid": "Загрузите файл.",
        },
    )


class DocumentSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    kind = serializers.CharField()
    filename = serializers.CharField(source="original_name")
    content_type = serializers.CharField()
    size = serializers.IntegerField()
    sha256 = serializers.CharField()
    uploaded_at = serializers.DateTimeField()
    download_url = serializers.SerializerMethodField()

    def get_download_url(self, document: Document) -> str:
        """Client route by default; bank views pass context["download_route"]."""
        path = reverse(
            self.context.get("download_route", "application-document-download"),
            kwargs={
                "application_id": document.application_id,
                "document_id": document.id,
            },
        )
        return self.context["request"].build_absolute_uri(path)
