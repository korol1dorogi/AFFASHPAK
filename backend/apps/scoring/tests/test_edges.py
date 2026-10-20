"""Edge cases on the scorecard level: D4 §8 Г1–Г10 and data-spec §10 edges (test-scenarios §6).

Where the generator builds the case (`edge_cases[]`), the input comes from it and the D4 number is
written here literally, then cross-checked with the record's `expected`. Cases marked «только
вход теста» (g4, g10, e_score_90_60_50) are built from literals.
"""

import pytest

from apps.scoring import build_input, score, stop_factors
from apps.scoring.tests.conftest import OK_TB, ON_DATE, bki, checks, company
from apps.scoring.tests.d4 import SNAPSHOTS, table_input


def scored(edge_case, code):
    inp, expected = edge_case(code)
    result = score(inp)
    for field in ("total", "grade"):
        if expected[field] is not None:
            assert getattr(result, field) == expected[field], (code, field)
    return result


def test_g1_dscr_exactly_on_threshold(edge_case):
    factor = scored(edge_case, "g1").factor("dscr")
    assert (str(factor.value), factor.points, factor.passed) == ("1.2500", 10, True)


def test_g3_total_exactly_75_is_b(edge_case):
    result = scored(edge_case, "g3")
    assert result.factor("bki_history").points == 8
    assert (result.total, result.grade) == (75, "B")


def test_g4_two_missing_key_metrics():
    snapshot = {
        **SNAPSHOTS["coffee_shop"],
        "revenue_trend": None,
        "counterparty_concentration": None,
    }
    result = score(build_input(company("ip", 36), snapshot, checks(), ON_DATE))
    assert tuple(f.points for f in result.factors) == (10, 25, 7, 7, 5, 20, 5)
    assert (result.total, result.grade) == (79, "B")
    assert result.missing_key_metrics == 2  # debt_service = 0 is not a missing metric


def test_g6_grade_e_with_bki_outage(edge_case):
    result = scored(edge_case, "g6")
    assert result.factor("bki_history").points == 10
    assert (result.total, result.grade) == (37, "E")


def test_g9_trend_exactly_08(edge_case):
    factor = scored(edge_case, "g9").factor("revenue_trend")
    assert (str(factor.value), factor.points, factor.passed) == ("0.8000", 4, False)


def test_g10_empty_registration_date():
    inp = build_input(company("ip", None), SNAPSHOTS["coffee_shop"], checks(), ON_DATE)
    assert stop_factors(inp) == []  # С5 cannot be checked: manual review (П3), not a decline
    result = score(inp)
    factor = result.factor("business_age_months")
    assert (factor.value, factor.points, factor.passed) == (None, 4, False)
    assert "Дату регистрации не получили из ЕГРЮЛ" in factor.message
    assert (result.total, result.grade) == (86, "B")
    assert result.missing_key_metrics == 0  # the age is not a key metric


def test_e_no_debt(edge_case):
    factor = scored(edge_case, "e_no_debt").factor("dscr")
    assert (factor.value, factor.points, factor.passed) == (None, 25, True)


def test_e_de_35_debt_to_ebitda_exactly_35(edge_case):
    result = scored(edge_case, "e_de_35")
    factor = result.factor("debt_to_ebitda")
    assert (str(factor.value), factor.points, factor.passed) == ("3.5000", 10, True)
    assert result.total == 88


@pytest.mark.parametrize(
    ("code", "points", "passed"),
    [("e_conc_edges_030", 10, True), ("e_conc_edges_050", 7, True), ("e_conc_edges_070", 3, False)],
)
def test_e_conc_edges(edge_case, code, points, passed):
    factor = scored(edge_case, code).factor("counterparty_concentration")
    assert (factor.points, factor.passed) == (points, passed)
    assert str(factor.value) == "0." + code[-2:] + "00"


def test_e_trend_090(edge_case):
    result = scored(edge_case, "e_trend_090")
    factor = result.factor("revenue_trend")
    assert (str(factor.value), factor.points, factor.passed) == ("0.9000", 10, True)
    assert result.total == 87


@pytest.mark.parametrize(
    ("code", "age", "points", "passed"),
    [
        ("e_age_edges_6", 6, 1, False),
        ("e_age_edges_12", 12, 4, True),
        ("e_age_edges_24", 24, 7, True),
        ("e_age_edges_36", 36, 10, True),
        ("e_short_history", 10, 1, False),
        ("e_young_wcl", 8, 1, False),
    ],
)
def test_e_age_edges(edge_case, code, age, points, passed):
    inp, _ = edge_case(code)
    assert stop_factors(inp) == []  # 6 months is not С5
    factor = scored(edge_case, code).factor("business_age_months")
    assert (factor.value, factor.points, factor.passed) == (age, points, passed)


def test_e_young_wcl_total(edge_case):
    result = scored(edge_case, "e_young_wcl")
    assert (result.total, result.grade) == (83, "B")


@pytest.mark.parametrize(
    ("code", "points", "passed", "total"),
    [("e_past_30_30", 8, True, 80), ("e_past_30_31", 3, False, 75)],
)
def test_e_past_30(edge_case, code, points, passed, total):
    result = scored(edge_case, code)
    factor = result.factor("bki_history")
    assert (factor.points, factor.passed) == (points, passed)
    assert (result.total, result.grade) == (total, "B")


def test_e_overdue_30_is_zero_points_not_a_stop(edge_case):
    inp, _ = edge_case("e_overdue_30_30")
    assert inp.check("bki").status == "warning"
    assert stop_factors(inp) == []
    result = scored(edge_case, "e_overdue_30_30")
    factor = result.factor("bki_history")
    assert (factor.points, factor.passed) == (0, False)
    assert (result.total, result.grade) == (72, "C")


def test_e_all_unavailable(edge_case):
    inp, _ = edge_case("e_all_unavailable")
    assert inp.snapshot is None
    result = scored(edge_case, "e_all_unavailable")
    assert tuple(f.points for f in result.factors) == (10, 12, 7, 7, 5, 10, 2)
    assert (result.total, result.grade) == (53, "D")
    assert result.missing_key_metrics == 3


# data-spec §10 «e_score_90_60_50 — входы для D5»: snapshot period 2026-09, unlisted fields null.
SCORE_EDGES = {
    90: (
        company("ooo", 60),
        {"cfads": "600000.00", "debt_service": "250000.00", "ebitda": "7500000.00",
         "debt": "23000000.00", "cash": "500000.00", "revenue_trend": "1.0500",
         "counterparty_concentration": "0.2000"},
        checks(transparent_business={
            "status": "warning",
            "data": {**OK_TB["data"], "tax_arrears": "50000.00"},
        }),
        (10, 25, 10, 15, 10, 20, 0), "A",
    ),
    60: (
        company("ip", 60),
        {"cfads": "400000.00", "debt_service": "250000.00", "revenue_trend": "0.9500",
         "counterparty_concentration": "0.4000"},
        checks(bki=bki(0, 15), transparent_business={
            "status": "warning",
            "data": {**OK_TB["data"], "tax_arrears": "20000.00"},
        }),
        (10, 18, 7, 10, 7, 8, 0), "C",
    ),
    50: (
        company("ip", 30),
        {"cfads": "300000.00", "debt_service": "220000.00", "revenue_trend": "0.9200",
         "counterparty_concentration": "0.6000"},
        checks(bki=bki(0, 20)),
        (7, 10, 7, 10, 3, 8, 5), "D",
    ),
}  # fmt: skip


@pytest.mark.parametrize("total", SCORE_EDGES)
def test_e_score_90_60_50(total):
    company_, snapshot, checks_, points, grade = SCORE_EDGES[total]
    result = score(build_input(company_, snapshot, checks_, ON_DATE))
    assert tuple(f.points for f in result.factors) == points
    assert (result.total, result.grade) == (total, grade)


def test_persona_1_literal_and_generated_inputs_agree(persona_input):
    """Guard for the two input paths: the same persona gives the same factors."""
    assert (
        score(table_input("coffee_shop")).factors_payload()
        == score(persona_input("coffee_shop")).factors_payload()
    )
