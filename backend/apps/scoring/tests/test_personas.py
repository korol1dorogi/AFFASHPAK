"""Personas 1–8: points of every factor, total and grade — exactly decision-model.md §8.

Two ways: (a) the §8 inputs as literals; (b) the persona data of the demo generator — proves the
chain «statement → snapshot → points».
"""

import pytest

from apps.scoring import build_input, improvements, score, stop_factors
from apps.scoring.tests.conftest import ON_DATE, UNAVAILABLE, company
from apps.scoring.tests.d4 import table_input

FACTORS = (
    "business_age_months", "dscr", "debt_to_ebitda", "revenue_trend",
    "counterparty_concentration", "bki_history", "transparent_business",
)  # fmt: skip

# D4 §8 «Баллы по факторам»: points in FACTORS order, total, grade.
EXPECTED = {
    "coffee_shop": ((10, 25, 7, 15, 10, 20, 5), 92, "A"),
    "retail_supplier": ((10, 25, 10, 15, 3, 20, 5), 88, "B"),
    "garden_store": ((10, 25, 7, 10, 10, 20, 5), 87, "B"),
    "furniture_maker": ((10, 18, 7, 10, 7, 8, 5), 65, "C"),
    "dependent_supplier": ((10, 4, 4, 4, 0, 20, 5), 47, "E"),
    "bki_outage": ((10, 25, 7, 15, 10, 10, 5), 82, "B"),
}
# ✗ of the table (passed = false); every other factor passed.
FAILED = {
    "coffee_shop": {"debt_to_ebitda"},  # None: no reporting — not computed, so not passed (§7)
    "retail_supplier": {"counterparty_concentration"},
    "garden_store": {"debt_to_ebitda"},
    "furniture_maker": {"debt_to_ebitda"},
    "dependent_supplier": {"dscr", "debt_to_ebitda", "revenue_trend", "counterparty_concentration"},
    "bki_outage": {"debt_to_ebitda", "bki_history"},
}


def assert_matches_d4(result, code: str) -> None:
    points, total, grade = EXPECTED[code]
    assert tuple(f.name for f in result.factors) == FACTORS
    assert tuple(f.points for f in result.factors) == points
    assert {f.name for f in result.factors if not f.passed} == FAILED[code]
    assert (result.total, result.grade) == (total, grade)
    assert result.model_version == "scorecard-2026.10-v1"
    assert result.missing_key_metrics == 0


@pytest.mark.parametrize("code", EXPECTED)
def test_persona_from_d4_table(code):
    assert_matches_d4(score(table_input(code)), code)


@pytest.mark.parametrize("code", EXPECTED)
def test_persona_from_generator(persona_input, code):
    # Persona 7's outage is DemoState(bki).failing (data-spec §5.2), not the JSON: set it here.
    overrides = {"bki": UNAVAILABLE} if code == "bki_outage" else {}
    assert_matches_d4(score(persona_input(code, **overrides)), code)


def test_persona_1_dscr_without_debt_passes_with_its_own_text():
    factor = score(table_input("coffee_shop")).factor("dscr")
    assert (factor.value, factor.points, factor.passed) == (None, 25, True)
    assert factor.message == "Долгов нет, и на счёт приходит больше денег, чем уходит"


@pytest.mark.parametrize(
    ("code", "dscr", "debt_to_ebitda"),
    [
        ("retail_supplier", "2.2000", "2.5714"),
        ("garden_store", "6.0000", None),
        ("furniture_maker", "1.8000", None),
        ("dependent_supplier", "1.1000", "4.2000"),
    ],
)
def test_persona_values_of_the_d4_table(persona_input, code, dscr, debt_to_ebitda):
    payload = {f["name"]: f["value"] for f in score(persona_input(code)).factors_payload()}
    assert (payload["dscr"], payload["debt_to_ebitda"]) == (dscr, debt_to_ebitda)


@pytest.mark.parametrize("source", ["table", "generator"])
def test_persona_6_is_stopped_by_c1_and_not_scored(persona_input, source):
    if source == "table":
        # §8: liquidating; checks are not requested — validation stops it by Company alone.
        inp = build_input(company("ooo", 60, "liquidating"), None, {}, ON_DATE)
    else:
        inp = persona_input("liquidating_company")
    assert [stop.code for stop in stop_factors(inp)] == ["С1"]
    assert stop_factors(inp)[0].reason.metric == "registry_status"
    with pytest.raises(ValueError, match="С1"):
        score(inp)


def test_persona_8_is_g7(edge_case):
    """D15: persona 8 `equipment_no_collateral` = data of Г7. The generator has no persona 8
    yet, so the Г7 edge case stands in for it."""
    inp, expected = edge_case("g7")
    result = score(inp)
    assert tuple(f.points for f in result.factors) == (10, 18, 7, 15, 7, 20, 5)
    assert (result.total, result.grade) == (82, "B")
    assert (expected["total"], expected["grade"]) == (82, "B")


def test_persona_5_improvements_by_lost_points():
    result = score(table_input("dependent_supplier"))
    lost = {f.name: f.lost_points for f in result.factors if not f.passed}
    assert lost == {
        "dscr": 21, "debt_to_ebitda": 11, "revenue_trend": 11, "counterparty_concentration": 10,
    }  # fmt: skip
    assert improvements(result) == [
        "Снизьте платежи по текущим долгам или увеличьте остаток денег после расходов",
        "Снизьте долг так, чтобы его можно было отдать из прибыли за 3,5 года или быстрее",
        "Верните выручку хотя бы к уровню прошлого года",
        "Найдите ещё покупателей, чтобы на крупнейшего приходилось не больше 50% поступлений",
    ]


def test_factors_payload_is_the_score_factor_schema():
    """ScoreFactor of openapi.yaml: exactly name, value (string | null), points, message."""
    payload = score(table_input("retail_supplier")).factors_payload()
    assert all(set(item) == {"name", "value", "points", "message"} for item in payload)
    by_name = {item["name"]: item for item in payload}
    assert by_name["dscr"]["value"] == "2.2000"
    assert by_name["business_age_months"]["value"] == "72"
    assert by_name["transparent_business"]["value"] is None
    assert all(isinstance(item["points"], int) for item in payload)
