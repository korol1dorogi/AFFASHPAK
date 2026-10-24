"""How much can be offered: DSCR-bound loan size, overdraft limit, factoring advance."""

from decimal import Decimal

from apps.credit_math.annuity import annuity_factor, annuity_payment
from apps.credit_math.money import Metric, Number, floor_rubles, precise, round_money, to_decimal

DEFAULT_MIN_DSCR = Decimal("1.25")


def max_payment_by_dscr(
    cfads: Number, current_debt_service: Number, min_dscr: Number = DEFAULT_MIN_DSCR
) -> Decimal:
    """A_max = CFADS / min_dscr − current debt service (unrounded, may be ≤ 0)."""
    flow = to_decimal(cfads, "cfads")
    current = to_decimal(current_debt_service, "current_debt_service")
    threshold = to_decimal(min_dscr, "min_dscr")
    if current < 0:
        raise ValueError("current_debt_service must be >= 0")
    if threshold <= 0:
        raise ValueError("min_dscr must be > 0")
    with precise():
        return flow / threshold - current


def max_loan_by_dscr(
    cfads: Number,
    current_debt_service: Number,
    annual_rate: Number,
    months: int,
    min_dscr: Number = DEFAULT_MIN_DSCR,
) -> Metric:
    """P_max = A_max · (1 − (1+r)^−n) / r, rounded down to whole rubles.

    Guarantees annuity_payment(P_max) ≤ A_max, so DSCR with the new payment ≥ min_dscr.
    A_max ≤ 0 → None: no loan should be offered.
    """
    a_max = max_payment_by_dscr(cfads, current_debt_service, min_dscr)
    if a_max <= 0:
        return Metric.unavailable(
            "Свободных денег на новый платёж не остаётся, поэтому кредит бизнесу сейчас "
            "не по силам."
        )
    with precise():
        principal = floor_rubles(a_max * annuity_factor(annual_rate, months))
    # Rounding the payment up to kopecks could push it over A_max on long terms; step down.
    while principal > 0 and annuity_payment(principal, annual_rate, months) > a_max:
        principal -= 1
    if principal <= 0:
        return Metric.unavailable("Сумма, которую потянет бизнес, меньше 1 рубля.")
    return Metric(principal)


def overdraft_limit(avg_monthly_cleaned_credit_turnover: Number, alpha: Number) -> Decimal:
    """Limit = alpha × average monthly cleaned credit turnover."""
    turnover = to_decimal(
        avg_monthly_cleaned_credit_turnover, "avg_monthly_cleaned_credit_turnover"
    )
    share = to_decimal(alpha, "alpha")
    if turnover < 0:
        raise ValueError("turnover must be >= 0")
    if not 0 < share <= 1:
        raise ValueError("alpha must be in (0, 1]")
    return round_money(turnover * share)


def factoring_advance(invoice_amount: Number, beta: Number) -> Decimal:
    """Advance = beta × shipment amount from the EDO document."""
    amount = to_decimal(invoice_amount, "invoice_amount")
    share = to_decimal(beta, "beta")
    if amount < 0:
        raise ValueError("invoice_amount must be >= 0")
    if not 0 < share <= 1:
        raise ValueError("beta must be in (0, 1]")
    return round_money(amount * share)


def factoring_commission(invoice_amount: Number, commission: Number) -> Decimal:
    """One-off factoring fee = commission × shipment amount (decision-model.md §5, flat fee)."""
    amount = to_decimal(invoice_amount, "invoice_amount")
    share = to_decimal(commission, "commission")
    if amount < 0:
        raise ValueError("invoice_amount must be >= 0")
    if not 0 <= share < 1:
        raise ValueError("commission must be in [0, 1)")
    return round_money(amount * share)
