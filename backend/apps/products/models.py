"""Product catalog (docs/data-model.md). Thresholds live in `params`, not in code."""

from django.db import models


class ProductKind(models.TextChoices):
    OVERDRAFT = "overdraft", "Овердрафт"
    FACTORING = "factoring", "Факторинг"
    WORKING_CAPITAL_LOAN = "working_capital_loan", "Кредит на пополнение оборотных средств"
    INVESTMENT_LOAN = "investment_loan", "Инвестиционный кредит"
    LEASING = "leasing", "Лизинг"


class Product(models.Model):
    code = models.SlugField(max_length=64, unique=True)
    kind = models.CharField(max_length=32, choices=ProductKind.choices)
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True, default="")
    rate_min = models.DecimalField(max_digits=8, decimal_places=4)
    rate_max = models.DecimalField(max_digits=8, decimal_places=4)
    term_min_months = models.PositiveIntegerField()
    term_max_months = models.PositiveIntegerField()
    amount_min = models.DecimalField(max_digits=14, decimal_places=2)
    amount_max = models.DecimalField(max_digits=14, decimal_places=2)
    is_revolving = models.BooleanField(default=False)
    collateral_required = models.BooleanField(default=False)
    params = models.JSONField(default=dict, blank=True, help_text="alpha, beta, min_dscr, …")
    requirements = models.JSONField(
        default=dict, blank=True, help_text="min_business_age_months, legal_forms"
    )
    required_documents = models.JSONField(default=list, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ("kind", "code")
        constraints = (
            models.CheckConstraint(
                condition=models.Q(rate_min__lte=models.F("rate_max")), name="product_rate_range"
            ),
            models.CheckConstraint(
                condition=models.Q(term_min_months__lte=models.F("term_max_months")),
                name="product_term_range",
            ),
            models.CheckConstraint(
                condition=models.Q(amount_min__lte=models.F("amount_max")),
                name="product_amount_range",
            ),
        )

    def __str__(self) -> str:
        return self.name
