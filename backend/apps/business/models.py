"""Company, its members, invitations and financial snapshots (docs/data-model.md).

The app label stays `business` (migrations already on the stand); the entity is Company.
"""

from django.conf import settings
from django.db import models
from django.db.models.functions import Lower
from django.utils import timezone


class LegalForm(models.TextChoices):
    IP = "ip", "ИП"
    OOO = "ooo", "ООО"


class RegistryStatus(models.TextChoices):
    ACTIVE = "active", "Действует"
    LIQUIDATING = "liquidating", "В процессе ликвидации"
    LIQUIDATED = "liquidated", "Ликвидирована"


class Company(models.Model):
    """ИП или ООО. Registry fields come from ЕГРЮЛ once and are not re-entered (F12)."""

    legal_form = models.CharField(max_length=3, choices=LegalForm.choices)
    name = models.CharField(max_length=300)
    inn = models.CharField(max_length=12, unique=True)
    ogrn = models.CharField(max_length=15)
    okved = models.CharField(max_length=16)
    okved_name = models.CharField(max_length=300, blank=True, default="")
    registered_at = models.DateField()
    region = models.CharField(max_length=128)
    address = models.CharField(max_length=500, blank=True, default="")
    registry_status = models.CharField(
        max_length=16, choices=RegistryStatus.choices, default=RegistryStatus.ACTIVE
    )
    director_name = models.CharField(max_length=200, blank=True, default="")
    # The client's own label for the interface; `name` stays the registry's legal name.
    short_name = models.CharField(max_length=300, blank=True, default="")
    is_demo = models.BooleanField(default=False)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        verbose_name = "компания"
        verbose_name_plural = "компании"

    def __str__(self) -> str:
        return self.name


class IntegrationSource(models.TextChoices):
    BANK_ACCOUNT = "bank_account", "Выписка по счёту"
    EDO = "edo", "ЭДО: документы отгрузки"


class CompanyIntegration(models.Model):
    """A connected data source (simulator) of a company and when it was connected."""

    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="integrations")
    source = models.CharField(max_length=16, choices=IntegrationSource.choices)
    connected_at = models.DateTimeField(default=timezone.now)

    class Meta:
        constraints = (
            models.UniqueConstraint(
                fields=("company", "source"), name="integration_company_source"
            ),
        )

    def __str__(self) -> str:
        return f"{self.company}: {self.source}"


class MemberRole(models.TextChoices):
    SIGNATORY = "signatory", "Подписант"
    PREPARER = "preparer", "Готовит заявку"


class Membership(models.Model):
    """User inside a company. Client scoping always goes through this table."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="memberships"
    )
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="memberships")
    role = models.CharField(max_length=16, choices=MemberRole.choices)
    position = models.CharField(max_length=100, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = (
            models.UniqueConstraint(fields=("user", "company"), name="membership_user_company"),
        )
        ordering = ("created_at", "id")

    def __str__(self) -> str:
        return f"{self.user} @ {self.company} ({self.role})"


class InvitationStatus(models.TextChoices):
    PENDING = "pending", "Ждёт ответа"
    ACCEPTED = "accepted", "Принято"
    DECLINED = "declined", "Отклонено"
    CANCELLED = "cancelled", "Отозвано"


class Invitation(models.Model):
    """A signatory invites a login into the company; Membership appears only on accept.

    The login is stored as typed and is not resolved to a user here: inviting answers the same
    whether such a client exists, works elsewhere or is a bank user (docs/security.md).
    """

    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="invitations")
    username = models.CharField(max_length=150)
    role = models.CharField(max_length=16, choices=MemberRole.choices)
    position = models.CharField(max_length=100)
    invited_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="+"
    )
    status = models.CharField(
        max_length=16, choices=InvitationStatus.choices, default=InvitationStatus.PENDING
    )
    created_at = models.DateTimeField(default=timezone.now)
    responded_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = (
            models.UniqueConstraint(
                Lower("username"),
                "company",
                condition=models.Q(status="pending"),
                name="invitation_pending_company_username",
            ),
        )
        ordering = ("created_at", "id")

    def __str__(self) -> str:
        return f"{self.username} → {self.company} ({self.status})"


class SnapshotSource(models.TextChoices):
    CASE = "case", "Данные кейса"
    DEMO = "demo", "Демо"
    SIMULATOR = "simulator", "Симулятор"
    MANUAL = "manual", "Вручную"


def _money(**kwargs):
    return models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True, **kwargs)


def _ratio(**kwargs):
    return models.DecimalField(max_digits=8, decimal_places=4, null=True, blank=True, **kwargs)


class FinancialSnapshot(models.Model):
    """Monthly figures for a period. null = unknown, never a fake 0 (AGENTS.md)."""

    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="snapshots")
    period = models.CharField(max_length=7, help_text="YYYY-MM")
    source = models.CharField(max_length=16, choices=SnapshotSource.choices)
    cleaned_credit_turnover = _money()
    cfads = _money()
    debt_service = _money()
    revenue = _money()
    cogs = _money()
    ebitda = _money()
    debt = _money()
    cash = _money()
    receivables = _money()
    inventory = _money()
    payables = _money()
    counterparty_concentration = _ratio()
    revenue_trend = _ratio()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-period", "-id")

    def __str__(self) -> str:
        return f"{self.company} {self.period}"
