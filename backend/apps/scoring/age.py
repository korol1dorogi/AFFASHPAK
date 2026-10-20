"""Business age for the scorecard and stop factor С5 (decision-model.md §4, «для D5»).

Not a money formula, so it lives here and not in credit_math.
"""

from datetime import date, datetime


def business_age_months(registered_at: date, on_date: date) -> int:
    """Full months between the dates: 2023-10-01 → 2026-10-01 is 36, → 2026-09-30 is 35.

    A month is full when the day of month is reached; 01-31 → 02-28 is 0 months.
    """
    if isinstance(registered_at, datetime) or isinstance(on_date, datetime):
        raise TypeError("pass dates, not datetimes: convert submitted_at in one place")
    if on_date < registered_at:
        raise ValueError("on_date is before registered_at")
    months = (on_date.year - registered_at.year) * 12 + on_date.month - registered_at.month
    if on_date.day < registered_at.day:
        months -= 1
    return months
