"""D4 §9: for every factor a worse metric, all else equal, never gives more points."""

import itertools

import pytest

from apps.scoring import build_input, score
from apps.scoring.tests.conftest import OK_TB, ON_DATE, bki, checks, company
from apps.scoring.tests.d4 import SNAPSHOTS

BASE = SNAPSHOTS["retail_supplier"]  # every metric is computed for this persona


def points_along(factor: str, inputs) -> list[int]:
    return [score(inp).factor(factor).points for inp in inputs]


def snapshot_input(**changes):
    return build_input(company("ooo", 72), {**BASE, **changes}, checks(), ON_DATE)


def assert_never_better(points: list[int]) -> None:
    assert all(later <= earlier for earlier, later in itertools.pairwise(points)), points


# Each grid goes from better to worse and steps on every boundary and next to it.
@pytest.mark.parametrize(
    ("factor", "field", "grid"),
    [
        ("dscr", "cfads", ["900000", "500000", "499999", "375000", "374999", "312500", "312499",
                           "250000", "249999", "1", "0", "-100000"]),
        ("debt_to_ebitda", "debt", ["600000", "14600000", "14600001", "25100000", "25100001",
                                    "35600000", "35600001", "90000000"]),
        ("revenue_trend", "revenue_trend", ["1.3000", "1.0000", "0.9999", "0.9000", "0.8999",
                                            "0.8000", "0.7999", "0.1000", "0"]),
        ("counterparty_concentration", "counterparty_concentration",
         ["0", "0.3000", "0.3001", "0.5000", "0.5001", "0.7000", "0.7001", "1.0000"]),
    ],
)  # fmt: skip
def test_snapshot_metrics(factor, field, grid):
    inputs = [snapshot_input(**{field: value}) for value in grid]
    points = points_along(factor, inputs)
    assert_never_better(points)
    assert_never_better([score(inp).total for inp in inputs])
    assert points[0] > points[-1]


def test_business_age():
    ages = [200, 37, 36, 35, 24, 23, 12, 11, 6]
    inputs = [build_input(company("ooo", age), BASE, checks(), ON_DATE) for age in ages]
    points = points_along("business_age_months", inputs)
    assert_never_better(points)
    assert points == [10, 10, 10, 7, 7, 4, 4, 1, 1]


def test_bki_history():
    worse = [(0, 0), (0, 1), (0, 30), (0, 31), (0, 120), (1, 1), (30, 30)]
    inputs = [
        build_input(company("ooo", 72), BASE, checks(bki=bki(current, past)), ON_DATE)
        for current, past in worse
    ]
    points = points_along("bki_history", inputs)
    assert_never_better(points)
    assert points == [20, 8, 8, 3, 3, 0, 0]


def test_transparent_business():
    variants = [
        {},
        {"mass_address": True},
        {"mass_director": True},
        {"mass_address": True, "mass_director": True},
        {"tax_arrears": "0.01"},
        {"mass_address": True, "tax_arrears": "100000.00"},
    ]
    inputs = [
        build_input(
            company("ooo", 72), BASE,
            checks(transparent_business={"status": "warning", "data": {**OK_TB["data"], **v}}),
            ON_DATE,
        )
        for v in variants
    ]  # fmt: skip
    points = points_along("transparent_business", inputs)
    assert_never_better(points)
    assert points == [5, 2, 2, 0, 0, 0]
