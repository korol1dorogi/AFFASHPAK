from django.db import models

from apps.applications.models import Application
from apps.documents.storage import document_upload_to


class DocumentKind(models.TextChoices):
    BANK_STATEMENT = "bank_statement", "Выписка"
    FINANCIAL_REPORT = "financial_report", "Отчётность"
    TAX_RETURN = "tax_return", "Декларация"
    CONTRACT = "contract", "Договор"
    INVOICE = "invoice", "Счёт"
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
