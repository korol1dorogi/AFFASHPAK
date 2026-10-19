"""All credit math lives here (docs/knowledge/credit.md). Pure functions, Decimal only, no Django.

Everything else in the project calls this module instead of re-implementing formulas.
"""

from apps.credit_math.annuity import (
    AnnuitySummary,
    ScheduleRow,
    annuity_factor,
    annuity_payment,
    annuity_schedule,
    annuity_summary,
)
from apps.credit_math.limits import (
    DEFAULT_MIN_DSCR,
    factoring_advance,
    max_loan_by_dscr,
    max_payment_by_dscr,
    overdraft_limit,
)
from apps.credit_math.metrics import (
    CashConversionCycle,
    ccc,
    counterparty_concentration,
    debt_to_ebitda,
    dscr,
    expected_loss,
    exposure_at_default,
    revenue_trend,
    working_capital_need,
)
from apps.credit_math.money import Metric, round_money, round_ratio, to_decimal
from apps.credit_math.reasons import Reason, check_at_least, check_at_most

__all__ = [
    "DEFAULT_MIN_DSCR",
    "AnnuitySummary",
    "CashConversionCycle",
    "Metric",
    "Reason",
    "ScheduleRow",
    "annuity_factor",
    "annuity_payment",
    "annuity_schedule",
    "annuity_summary",
    "ccc",
    "check_at_least",
    "check_at_most",
    "counterparty_concentration",
    "debt_to_ebitda",
    "dscr",
    "expected_loss",
    "exposure_at_default",
    "factoring_advance",
    "max_loan_by_dscr",
    "max_payment_by_dscr",
    "overdraft_limit",
    "revenue_trend",
    "round_money",
    "round_ratio",
    "to_decimal",
    "working_capital_need",
]
