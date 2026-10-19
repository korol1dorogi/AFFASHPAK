from django.db import models

from apps.business.models import Business


class NeedType(models.TextChoices):
    CASH_GAP = "cash_gap", "Кассовый разрыв"
    RECEIVABLE_DELAY = "receivable_delay", "Отсрочка покупателя"
    WORKING_CAPITAL = "working_capital", "Оборотные средства"
    CAPEX = "capex", "Инвестиции"


class ApplicationStatus(models.TextChoices):
    DRAFT = "draft", "Черновик"
    SUBMITTED = "submitted", "Отправлена"
    IN_REVIEW = "in_review", "На рассмотрении"
    APPROVED = "approved", "Одобрена"
    DECLINED = "declined", "Отказ"
    INFO_REQUESTED = "info_requested", "Нужны документы"
    CANCELLED = "cancelled", "Отозвана"


class PrefillSource(models.TextChoices):
    MANUAL = "manual", "Вручную"
    RECOMMENDATION = "recommendation", "Подбор"
    ASSISTANT = "assistant", "Ассистент"


class Application(models.Model):
    """Credit application. Status changes only through the state machine, not this API.

    The product catalog (domain.md Product) is not in the tree yet, so there is no
    product foreign key. Documents only need the owning business.
    """

    business = models.ForeignKey(
        Business,
        on_delete=models.PROTECT,
        related_name="applications",
    )
    need_type = models.CharField(max_length=32, choices=NeedType.choices)
    purpose = models.TextField()
    requested_amount = models.DecimalField(max_digits=14, decimal_places=2)
    term_months = models.PositiveIntegerField()
    status = models.CharField(
        max_length=32,
        choices=ApplicationStatus.choices,
        default=ApplicationStatus.DRAFT,
    )
    prefill_source = models.CharField(
        max_length=32,
        choices=PrefillSource.choices,
        default=PrefillSource.MANUAL,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    submitted_at = models.DateTimeField(null=True, blank=True)

    def __str__(self) -> str:
        return f"Application {self.pk}"
