"""Annuity loans: payment, schedule, inverse (principal from payment)."""

from dataclasses import dataclass
from decimal import Decimal

from apps.credit_math.money import Number, precise, round_money, to_decimal


def _validate(principal: Decimal, annual_rate: Decimal, months: int) -> None:
    if principal < 0:
        raise ValueError("principal must be >= 0")
    if annual_rate < 0:
        raise ValueError("annual_rate must be >= 0 (annual, as a fraction: 0.24)")
    if isinstance(months, bool) or not isinstance(months, int) or months < 1:
        raise ValueError("months must be an integer >= 1")


def monthly_rate(annual_rate: Decimal) -> Decimal:
    return annual_rate / 12


def annuity_factor(annual_rate: Number, months: int) -> Decimal:
    """Present value of 1 ruble paid monthly for `months`: (1 - (1+r)^-n) / r; n when r = 0."""
    rate = to_decimal(annual_rate, "annual_rate")
    _validate(Decimal(0), rate, months)
    with precise():
        r = monthly_rate(rate)
        if r == 0:
            return Decimal(months)
        return (1 - (1 + r) ** -months) / r


def annuity_payment_exact(principal: Number, annual_rate: Number, months: int) -> Decimal:
    """Unrounded payment; use annuity_payment() for anything shown or stored."""
    p = to_decimal(principal, "principal")
    rate = to_decimal(annual_rate, "annual_rate")
    _validate(p, rate, months)
    with precise():
        return p / annuity_factor(rate, months)


def annuity_payment(principal: Number, annual_rate: Number, months: int) -> Decimal:
    """A = P·r / (1 − (1+r)^−n); r = 0 → P/n. Rounded to kopecks.

    >>> annuity_payment(Decimal("1000000"), Decimal("0.24"), 12)
    Decimal('94559.60')
    """
    return round_money(annuity_payment_exact(principal, annual_rate, months))


@dataclass(frozen=True)
class ScheduleRow:
    number: int
    payment: Decimal
    interest: Decimal
    principal: Decimal
    balance: Decimal


@dataclass(frozen=True)
class AnnuitySummary:
    payment: Decimal
    total_paid: Decimal
    overpayment: Decimal
    schedule: list[ScheduleRow]


def annuity_schedule(principal: Number, annual_rate: Number, months: int) -> list[ScheduleRow]:
    """Repayment schedule: interest = balance·r (to kopecks), principal = A − interest.

    The last payment absorbs the kopeck remainder, so the principal parts sum to P exactly.
    """
    p = to_decimal(principal, "principal")
    rate = to_decimal(annual_rate, "annual_rate")
    _validate(p, rate, months)
    payment = annuity_payment(p, rate, months)
    r = monthly_rate(rate)

    rows: list[ScheduleRow] = []
    balance = round_money(p)
    for number in range(1, months + 1):
        interest = round_money(balance * r)
        if number == months:
            principal_part = balance
            row_payment = principal_part + interest
        else:
            principal_part = min(payment - interest, balance)
            row_payment = principal_part + interest
        balance -= principal_part
        rows.append(
            ScheduleRow(
                number=number,
                payment=row_payment,
                interest=interest,
                principal=principal_part,
                balance=balance,
            )
        )
    return rows


def annuity_summary(principal: Number, annual_rate: Number, months: int) -> AnnuitySummary:
    """Payment, total paid and overpayment computed from the actual schedule."""
    p = round_money(to_decimal(principal, "principal"))
    schedule = annuity_schedule(p, annual_rate, months)
    total_paid = sum((row.payment for row in schedule), Decimal("0.00"))
    return AnnuitySummary(
        payment=annuity_payment(p, annual_rate, months),
        total_paid=total_paid,
        overpayment=total_paid - p,
        schedule=schedule,
    )
