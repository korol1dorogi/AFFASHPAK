"""Arithmetic of building data, not credit metrics: rounding steps, quotas, splits, months.

Credit metrics live in apps.credit_math; this module only shapes generated amounts so that the
metrics come out exactly (docs/data-spec.md §4.4: r1000, last posting takes the remainder).
"""

import calendar
from collections.abc import Sequence
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

KOPECK = Decimal("0.01")


def round_to(value: Decimal, step: int) -> Decimal:
    """Round to a whole number of `step` rubles, ROUND_HALF_UP: r1, r1000, r10000, r50000."""
    return (Decimal(value) / step).quantize(Decimal(1), rounding=ROUND_HALF_UP) * step


def r1(value: Decimal) -> Decimal:
    return round_to(value, 1)


def r1000(value: Decimal) -> Decimal:
    return round_to(value, 1000)


def money(value: Decimal | int) -> str:
    """Money as the JSON string with two decimals."""
    return str(Decimal(value).quantize(KOPECK, rounding=ROUND_HALF_UP))


def largest_remainder(total: int, weights: Sequence[Decimal]) -> list[int]:
    """Split `total` into integers proportional to `weights`; ties go to the earlier row."""
    weight_sum = sum(weights, Decimal(0))
    if total < 0 or weight_sum <= 0:
        raise ValueError("total must be >= 0 and weights must have a positive sum")
    exact = [Decimal(total) * w / weight_sum for w in weights]
    counts = [int(x) for x in exact]
    by_remainder = sorted(range(len(weights)), key=lambda i: (-(exact[i] - counts[i]), i))
    for i in by_remainder[: total - sum(counts)]:
        counts[i] += 1
    return counts


def split_amount(total: Decimal, weights: Sequence[int]) -> list[Decimal]:
    """Split money into parts proportional to integer weights; the last part takes the rest.

    Every part is > 0 as long as the total has at least one kopeck per part.
    """
    if not weights or min(weights) <= 0:
        raise ValueError("weights must be positive")
    kopecks = int((Decimal(total) / KOPECK).to_integral_value())
    if kopecks < len(weights):
        raise ValueError("total is too small to give every part a kopeck")
    weight_sum = sum(weights)
    parts = [max(1, kopecks * w // weight_sum) for w in weights[:-1]]
    parts.append(kopecks - sum(parts))
    if parts[-1] <= 0:
        raise ValueError("cannot split the total into positive parts")
    return [Decimal(p) * KOPECK for p in parts]


def add_months(day: date, months: int) -> date:
    """Same day of month `months` later (earlier if negative), clamped to the month's end."""
    index = day.year * 12 + day.month - 1 + months
    year, month = divmod(index, 12)
    month += 1
    return date(year, month, min(day.day, calendar.monthrange(year, month)[1]))


def month_days(period: str) -> int:
    year, month = (int(part) for part in period.split("-"))
    return calendar.monthrange(year, month)[1]


def month_start(period: str) -> date:
    year, month = (int(part) for part in period.split("-"))
    return date(year, month, 1)


def full_months_between(start: date, end: date) -> int:
    """Whole months from `start` to `end` (end exclusive)."""
    months = (end.year - start.year) * 12 + end.month - start.month
    return months - 1 if end.day < start.day else months
