"""Statement plan edge cases (data-spec.md §4.4, steps 6–7)."""

from decimal import Decimal

import pytest

from apps.demo_data.build import generate
from apps.demo_data.reference import GROUPS_BY_CODE
from apps.demo_data.statements import MIN_PAYER_AMOUNT, Payer, StatementPlan, payer_months

D = Decimal


def plan(**fields) -> StatementPlan:
    defaults = {
        "company_key": "co_demo",
        "legal_form": "ooo",
        "inn": "0000000000",
        "group": GROUPS_BY_CODE["garden"],
        "months": tuple(f"2025-{m:02d}" for m in range(1, 13)),
        "window_sum": D(0),
        "cfads": D(0),
        "tau": None,
        "kappa": D("0.39"),
        "top_payer": "ООО «Крупный» (демо)",
        "other_payers": [Payer(f"ООО «Мелкий {j}» (демо)", D("0.008")) for j in range(6)],
        "has_retail": True,
        "suppliers": [],
        "landlord": "ООО «Арендодатель» (демо)",
    }
    return StatementPlan(**{**defaults, **fields})


def test_tiny_payer_in_a_dead_month_pays_the_smallest_unit_from_retail():
    """Seed 2028, co_2026: 0.8 % of a 52 000 ₽ month rounded to 0 and the generator failed."""
    revenue = [D(v) for v in (1567000, 1138000, 88000, 61000, 61000, 52000, 70000, 157600,
                              2530000, 3088000, 2662000, 3447000)]  # fmt: skip
    totals = payer_months(plan(), revenue)
    dead = 5
    assert all(series[dead] == MIN_PAYER_AMOUNT for series in totals.others)
    assert totals.retail[dead] == revenue[dead] - totals.top_payer[dead] - 6 * MIN_PAYER_AMOUNT
    for k, month in enumerate(revenue):
        assert totals.top_payer[k] + sum(s[k] for s in totals.others) + totals.retail[k] == month


def test_ordinary_months_are_untouched():
    revenue = [D(3_000_000)] * 12
    totals = payer_months(plan(), revenue)
    assert all(series[0] == D(24000) for series in totals.others)  # 0.008 × 3 000 000


@pytest.mark.slow
def test_seed_2028_generates():
    """data-spec.md §11.5 checks stability on seed 2028; it used to fail on co_2026."""
    data = generate(seed=2028, n_companies=2027)
    assert any(company["_key"] == "co_2026" for company in data["companies"])
