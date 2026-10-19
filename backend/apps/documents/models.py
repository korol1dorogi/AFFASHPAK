from django.conf import settings
from django.db import models

from apps.applications.models import Application, InfoRequest
from apps.documents.storage import document_upload_to


class DocumentKind(models.TextChoices):
    BANK_STATEMENT = "bank_statement", "Выписка"
    FINANCIAL_REPORT = "financial_report", "Отчётность"
    TAX_RETURN = "tax_return", "Декларация"
    CONTRACT = "contract", "Договор"
    INVOICE = "invoice", "Счёт"
    SHIPMENT_DOCUMENT = "shipment_document", "Документ отгрузки (УПД)"
    OTHER = "other", "Другое"


class Document(models.Model):
    application = models.ForeignKey(
        Application,
        on_delete=models.CASCADE,
        related_name="documents",
    )
    kind = models.CharField(max_length=32, choices=DocumentKind.choices)
    file = models.FileField(upload_to=document_upload_to)
    original_name = models.CharField(max_length=255)
    content_type = models.CharField(max_length=128)
    size = models.PositiveIntegerField()
    sha256 = models.CharField(max_length=64)
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    info_request = models.ForeignKey(
        InfoRequest, on_delete=models.SET_NULL, null=True, blank=True, related_name="documents"
    )
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = (
            models.CheckConstraint(
                condition=models.Q(size__gte=1),
                name="document_size_gte_1",
            ),
        )
        ordering = ("uploaded_at", "id")

    def __str__(self) -> str:
        return self.original_name
