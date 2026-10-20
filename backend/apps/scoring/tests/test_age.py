from datetime import date, datetime

import pytest

from apps.scoring import business_age_months


@pytest.mark.parametrize(
    ("registered_at", "on_date", "months"),
    [
        (date(2023, 10, 1), date(2026, 10, 1), 36),  # persona 1 on as_of
        (date(2023, 10, 1), date(2026, 9, 30), 35),
        (date(2023, 10, 15), date(2026, 10, 14), 35),
        (date(2023, 10, 15), date(2026, 10, 15), 36),
        (date(2026, 1, 31), date(2026, 2, 28), 0),  # the day of month is not reached
        (date(2026, 1, 31), date(2026, 3, 31), 2),
        (date(2025, 12, 1), date(2026, 1, 1), 1),
        (date(2026, 10, 1), date(2026, 10, 1), 0),
    ],
)
def test_full_months(registered_at, on_date, months):
    assert business_age_months(registered_at, on_date) == months


def test_on_date_before_registration_is_an_error():
    with pytest.raises(ValueError):
        business_age_months(date(2026, 10, 2), date(2026, 10, 1))


def test_datetime_is_rejected():
    with pytest.raises(TypeError):
        business_age_months(date(2023, 10, 1), datetime(2026, 10, 1, 12))  # noqa: DTZ001
