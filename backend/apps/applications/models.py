"""Application and everything around it (docs/data-model.md, docs/state-machine.md).

`status` and `version` are written only by apps.applications.services.transitions.
"""

from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.business.models import Company
from apps.products.models import Product

USER = settings.AUTH_USER_MODEL


def _money(**kwargs):
    return models.DecimalField(max_digits=14, decimal_places=2, **kwargs)


class NeedType(models.TextChoices):
    CASH_GAP = "cash_gap", "Кассовый разрыв"
    RECEIVABLE_DELAY = "receivable_delay", "Покупатель платит позже"
    WORKING_CAPITAL = "working_capital", "Оборотные средства"
    CAPEX = "capex", "Инвестиции"


class ApplicationStatus(models.TextChoices):
    DRAFT = "draft", "Черновик"
    SUBMITTED = "submitted", "Отправлена"
    PROCESSING = "processing", "Проверяем"
    MANUAL_REVIEW = "manual_review", "У сотрудника банка"
    INFO_REQUESTED = "info_requested", "Нужны уточнения"
    OFFER = "offer", "Есть предложение"
    SIGNING = "signing", "Подписание"
    SIGNED = "signed", "Договор подписан"
    ISSUED = "issued", "Деньги выданы"
    DECLINED = "declined", "Отказ"
    CANCELLED = "cancelled", "Отозвана"


class PrefillSource(models.TextChoices):
    MANUAL = "manual", "Вручную"
    RECOMMENDATION = "recommendation", "Подбор"
    ASSISTANT = "assistant", "Ассистент"


class Application(models.Model):
    company = models.ForeignKey(Company, on_delete=models.PROTECT, related_name="applications")
    created_by = models.ForeignKey(
        USER, on_delete=models.PROTECT, null=True, blank=True, related_name="+"
    )
    need_type = models.CharField(max_length=32, choices=NeedType.choices)
    purpose = models.TextField()
    product = models.ForeignKey(
        Product, on_delete=models.PROTECT, null=True, blank=True, related_name="applications"
    )
    requested_amount = _money()
    term_months = models.PositiveIntegerField()
    invoice_amount = _money(null=True, blank=True)
    collateral_description = models.TextField(null=True, blank=True)  # noqa: DJ001 - null means «not set» in the contract
    status = models.CharField(
        max_length=32, choices=ApplicationStatus.choices, default=ApplicationStatus.DRAFT
    )
    version = models.PositiveIntegerField(default=0)
    assignee = models.ForeignKey(
        USER, on_delete=models.SET_NULL, null=True, blank=True, related_name="assigned_applications"
    )
    prefill_source = models.CharField(
        max_length=32, choices=PrefillSource.choices, default=PrefillSource.MANUAL
    )
    source_unavailable = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    status_changed_at = models.DateTimeField(default=timezone.now)
    decided_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("-created_at", "-id")
        indexes = (models.Index(fields=("status", "status_changed_at")),)
        constraints = (
            models.CheckConstraint(
                condition=models.Q(requested_amount__gt=0), name="application_amount_positive"
            ),
            models.CheckConstraint(
                condition=models.Q(term_months__gte=1), name="application_term_positive"
            ),
        )

    def __str__(self) -> str:
        return f"Заявка {self.pk}"


class IdempotencyKey(models.Model):
    """Stored response of an idempotent call: same (user, key) → same answer, no new transition."""

    user = models.ForeignKey(USER, on_delete=models.CASCADE, related_name="+")
    key = models.UUIDField()
    endpoint = models.CharField(max_length=200)
    response_status = models.PositiveSmallIntegerField()
    response_body = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = (
            models.UniqueConstraint(fields=("user", "key"), name="idempotency_user_key"),
        )

    def __str__(self) -> str:
        return f"{self.endpoint} {self.key}"


# Version of the consent text the client saw (frontend/src/texts BKI_CONSENT). A new wording →
# a new version here and in texts; an old version on submit is a 400.
BKI_CONSENT_VERSION = "bki-2026-10"


class BkiConsent(models.Model):
    """Consent to request the credit history from a credit bureau (218-FZ, art. 6). Given by the
    signatory on submit; without it the pipeline does not call the bureau."""

    application = models.OneToOneField(
        Application, on_delete=models.CASCADE, related_name="bki_consent"
    )
    user = models.ForeignKey(USER, on_delete=models.PROTECT, related_name="+")
    text_version = models.CharField(max_length=32)
    given_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return f"{self.application_id}: {self.text_version}"


class ActorKind(models.TextChoices):
    CLIENT = "client", "Клиент"
    BANK = "bank", "Банк"
    SYSTEM = "system", "Система"


class EventKind(models.TextChoices):
    STATUS_CHANGED = "status_changed", "Смена статуса"
    DOCUMENT_UPLOADED = "document_uploaded", "Документ загружен"
    INFO_REQUESTED = "info_requested", "Запрос информации"
    INFO_RESPONDED = "info_responded", "Ответ на запрос"
    ASSIGNED = "assigned", "Назначен сотрудник"
    CHECK_COMPLETED = "check_completed", "Проверка выполнена"
    SCORE_CALCULATED = "score_calculated", "Скоринг"
    DECISION = "decision", "Решение"
    COMMENT = "comment", "Комментарий"
    SIGNED = "signed", "Подписано"
    ISSUED = "issued", "Выдано"
    CONSENT_GIVEN = "consent_given", "Согласие на запрос в БКИ"


class ApplicationEvent(models.Model):
    """Audit journal, append-only. `is_internal` events are never shown to the client."""

    application = models.ForeignKey(Application, on_delete=models.CASCADE, related_name="events")
    kind = models.CharField(max_length=32, choices=EventKind.choices)
    # null: the event did not change the status (document uploaded, comment…)
    from_status = models.CharField(  # noqa: DJ001
        max_length=32, choices=ApplicationStatus.choices, null=True, blank=True
    )
    to_status = models.CharField(  # noqa: DJ001
        max_length=32, choices=ApplicationStatus.choices, null=True, blank=True
    )
    actor_kind = models.CharField(max_length=8, choices=ActorKind.choices)
    actor = models.ForeignKey(USER, on_delete=models.SET_NULL, null=True, blank=True)
    message = models.TextField(blank=True, default="")
    payload = models.JSONField(default=dict, blank=True)
    is_internal = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("created_at", "id")

    def __str__(self) -> str:
        return f"{self.application_id}: {self.kind}"


class CheckSource(models.TextChoices):
    EGRUL = "egrul", "ЕГРЮЛ/ЕГРИП"
    TRANSPARENT_BUSINESS = "transparent_business", "«Прозрачный бизнес»"
    BKI = "bki", "БКИ"
    BANK_ACCOUNT = "bank_account", "Счёт в банке"


class CheckStatus(models.TextChoices):
    OK = "ok", "Ок"
    WARNING = "warning", "Внимание"
    FAILED = "failed", "Не пройдена"
    UNAVAILABLE = "unavailable", "Источник недоступен"
    NOT_FOUND = "not_found", "Нет в реестре"
    RESTRICTED = "restricted", "Сведения скрыты"
    CONSENT_MISSING = "consent_missing", "Нет согласия клиента"


class Check(models.Model):
    application = models.ForeignKey(Application, on_delete=models.CASCADE, related_name="checks")
    source = models.CharField(max_length=32, choices=CheckSource.choices)
    status = models.CharField(max_length=16, choices=CheckStatus.choices)
    summary = models.TextField(blank=True, default="")
    data = models.JSONField(default=dict, blank=True)
    duration_ms = models.PositiveIntegerField(null=True, blank=True)
    checked_at = models.DateTimeField(auto_now_add=True)
    # Provenance (SRC4): when the answer came, its sha256 and the simulator version.
    # Null when the source did not answer (unavailable, consent_missing).
    received_at = models.DateTimeField(null=True, blank=True)
    response_sha256 = models.CharField(max_length=64, null=True, blank=True)  # noqa: DJ001 - null means «no answer» in the contract
    simulator_version = models.CharField(max_length=64, null=True, blank=True)  # noqa: DJ001 - null means «no answer» in the contract

    class Meta:
        ordering = ("checked_at", "id")

    def __str__(self) -> str:
        return f"{self.application_id}: {self.source} {self.status}"


class Grade(models.TextChoices):
    A = "A", "A"
    B = "B", "B"
    C = "C", "C"
    D = "D", "D"
    E = "E", "E"


class Score(models.Model):
    application = models.OneToOneField(Application, on_delete=models.CASCADE, related_name="score")
    grade = models.CharField(max_length=1, choices=Grade.choices)
    total = models.IntegerField()
    factors = models.JSONField(default=list)
    model_version = models.CharField(max_length=32)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return f"{self.application_id}: {self.grade}"


class DecisionOutcome(models.TextChoices):
    OFFER = "offer", "Предложение"
    COUNTEROFFER = "counteroffer", "Иные условия"
    ALTERNATIVE_PRODUCT = "alternative_product", "Другой продукт"
    MANUAL_REVIEW = "manual_review", "Ручное рассмотрение"
    INFO_REQUESTED = "info_requested", "Запрос информации"
    DECLINED = "declined", "Отказ"


class DecidedBy(models.TextChoices):
    AUTO = "auto", "Автоматически"
    OFFICER = "officer", "Сотрудник банка"


class Decision(models.Model):
    application = models.ForeignKey(Application, on_delete=models.CASCADE, related_name="decisions")
    outcome = models.CharField(max_length=32, choices=DecisionOutcome.choices)
    decided_by = models.CharField(max_length=8, choices=DecidedBy.choices)
    officer = models.ForeignKey(USER, on_delete=models.SET_NULL, null=True, blank=True)
    grade = models.CharField(max_length=1, choices=Grade.choices, null=True, blank=True)  # noqa: DJ001 - null means «not set» in the contract
    policy_version = models.CharField(max_length=32)
    reasons = models.JSONField(default=list, blank=True)
    improvements = models.JSONField(default=list, blank=True)
    comment = models.TextField(null=True, blank=True)  # noqa: DJ001 - null means «not set» in the contract
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("created_at", "id")

    def __str__(self) -> str:
        return f"{self.application_id}: {self.outcome} ({self.decided_by})"


class OfferStatus(models.TextChoices):
    ACTIVE = "active", "Действует"
    ACCEPTED = "accepted", "Принято"
    DECLINED = "declined", "Отклонено"
    SUPERSEDED = "superseded", "Заменено"


class Offer(models.Model):
    decision = models.OneToOneField(Decision, on_delete=models.CASCADE, related_name="offer")
    application = models.ForeignKey(Application, on_delete=models.CASCADE, related_name="offers")
    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name="+")
    amount = _money()
    requested_amount = _money()
    term_months = models.PositiveIntegerField()
    rate = models.DecimalField(max_digits=8, decimal_places=4)
    monthly_payment = _money(null=True, blank=True)
    is_counteroffer = models.BooleanField(default=False)
    product_changed = models.BooleanField(default=False)
    reasons = models.JSONField(default=list, blank=True)
    status = models.CharField(
        max_length=16, choices=OfferStatus.choices, default=OfferStatus.ACTIVE
    )
    expires_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at", "-id")
        constraints = (
            models.UniqueConstraint(
                fields=("application",),
                condition=models.Q(status="active"),
                name="offer_one_active_per_application",
            ),
        )

    def __str__(self) -> str:
        return f"{self.application_id}: {self.amount} ₽, {self.status}"


class InfoRequestOrigin(models.TextChoices):
    VALIDATION = "validation", "Проверка полноты"
    OFFICER = "officer", "Сотрудник банка"


class InfoRequestStatus(models.TextChoices):
    OPEN = "open", "Открыт"
    ANSWERED = "answered", "Отвечен"


class InfoRequest(models.Model):
    application = models.ForeignKey(
        Application, on_delete=models.CASCADE, related_name="info_requests"
    )
    origin = models.CharField(max_length=16, choices=InfoRequestOrigin.choices)
    requested_by = models.ForeignKey(
        USER, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    message = models.TextField()
    fields = models.JSONField(default=list, blank=True)
    document_kinds = models.JSONField(default=list, blank=True)
    status = models.CharField(
        max_length=16, choices=InfoRequestStatus.choices, default=InfoRequestStatus.OPEN
    )
    response_message = models.TextField(null=True, blank=True)  # noqa: DJ001 - null means «not set» in the contract
    answered_by = models.ForeignKey(
        USER, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    answered_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("created_at", "id")

    def __str__(self) -> str:
        return f"{self.application_id}: {self.origin} {self.status}"


class Signature(models.Model):
    """On-screen code instead of SMS (O5). Only a hash of the code is stored."""

    application = models.OneToOneField(
        Application, on_delete=models.CASCADE, related_name="signature"
    )
    code_hash = models.CharField(max_length=256)
    expires_at = models.DateTimeField()
    attempts_left = models.PositiveSmallIntegerField()
    signed_at = models.DateTimeField(null=True, blank=True)
    signed_by = models.ForeignKey(
        USER, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )

    def __str__(self) -> str:
        return f"Подпись заявки {self.application_id}"


class DisbursementStatus(models.TextChoices):
    PENDING = "pending", "В обработке"
    DONE = "done", "Выполнено"
    FAILED = "failed", "Ошибка"


class Disbursement(models.Model):
    """Simulated money transfer (O6)."""

    application = models.OneToOneField(
        Application, on_delete=models.CASCADE, related_name="disbursement"
    )
    amount = _money()
    account_masked = models.CharField(max_length=32, blank=True, default="")
    status = models.CharField(
        max_length=16, choices=DisbursementStatus.choices, default=DisbursementStatus.PENDING
    )
    issued_at = models.DateTimeField(null=True, blank=True)

    def __str__(self) -> str:
        return f"Выдача по заявке {self.application_id}: {self.status}"
