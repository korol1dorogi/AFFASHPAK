"""Rate by grade (decision-model.md §5): linear from rate_min (A) to rate_max (E).

Ranges are the D3 catalog; the same grade gives different rates for different products (F8).
"""

from decimal import Decimal

import pytest

from apps.applications.offers import rate_for
from apps.products.models import Product

D = Decimal


def product(rate_min: str, rate_max: str) -> Product:
    return Product(rate_min=D(rate_min), rate_max=D(rate_max))


@pytest.mark.parametrize(
    ("rate_min", "rate_max", "grade", "expected"),
    [
        ("0.20", "0.32", "A", "0.2000"),  # overdraft, persona 1
        ("0.22", "0.30", "B", "0.2400"),  # working capital loan, persona 3 counteroffer
        ("0.19", "0.28", "C", "0.2350"),  # investment loan, persona 4
        ("0.20", "0.30", "B", "0.2250"),  # leasing, persona 8
        ("0.20", "0.30", "E", "0.3000"),
    ],
)
def test_rate_by_grade_matches_decision_model(rate_min, rate_max, grade, expected):
    assert rate_for(product(rate_min, rate_max), grade) == D(expected)


@pytest.mark.parametrize("grade", [None, "", "Z"])
def test_unknown_grade_gets_the_highest_rate(grade):
    assert rate_for(product("0.20", "0.30"), grade) == D("0.30")
