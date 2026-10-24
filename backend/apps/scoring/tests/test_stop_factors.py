"""Stop factors С1–С5 (decision-model.md §2): found before scoring; stopped means not scored."""

from datetime import date

import pytest

from apps.scoring import build_input, score, stop_factors
from apps.scoring.tests.conftest import ON_DATE, UNAVAILABLE, bki, checks, company
from apps.scoring.tests.d4 import SNAPSHOTS


def codes(inp) -> list[str]:
    return [stop.code for stop in stop_factors(inp)]


def test_personas_1_to_5_and_7_have_no_stop_factors(persona_input):
    for code in ("coffee_shop", "retail_supplier", "garden_store", "furniture_maker",
                 "dependent_supplier", "bki_outage"):  # fmt: skip
        assert codes(persona_input(code)) == [], code


def test_c1_liquidating_at_validation_by_company_alone():
    inp = build_input(company("ooo", 60, "liquidating"), None, {}, ON_DATE)
    (stop,) = stop_factors(inp)
    assert stop.code == "С1"
    assert stop.reason.as_dict() == {
        "metric": "registry_status", "value": None, "threshold": None, "passed": False,
        "message": "По данным ЕГРЮЛ компания ликвидируется, поэтому кредит выдать нельзя",
    }  # fmt: skip
    assert stop.improvement is None


def test_c1_from_egrul_answer_at_enrichment():
    egrul = {"status": "warning", "data": {"registry_status": "liquidated"}}
    inp = build_input(company("ooo", 60), SNAPSHOTS["coffee_shop"], checks(egrul=egrul), ON_DATE)
    assert codes(inp) == ["С1"]


def test_g5_stop_wins_over_outage(edge_case):
    inp, expected = edge_case("g5")
    assert codes(inp) == ["С1"]
    assert expected["outcome"] == "declined"


def test_c2_not_in_registry():
    egrul = {"status": "failed", "data": {}}
    inp = build_input(company("ooo", 60), SNAPSHOTS["coffee_shop"], checks(egrul=egrul), ON_DATE)
    (stop,) = stop_factors(inp)
    assert (stop.code, stop.reason.metric, stop.improvement) == (
        "С2", "egrul_found", "Проверьте ИНН компании",
    )  # fmt: skip


@pytest.mark.parametrize(("code", "ebitda"), [("g8", "0.00"), ("e_ebitda_negative", "-500000.00")])
def test_c3_non_positive_ebitda(edge_case, code, ebitda):
    inp, expected = edge_case(code)
    assert str(inp.metric("ebitda")) == ebitda
    (stop,) = stop_factors(inp)
    assert (stop.code, stop.reason.metric, stop.reason.passed) == ("С3", "ebitda", False)
    assert expected["outcome"] == "declined"
    with pytest.raises(ValueError, match="С3"):
        score(inp)


def test_c3_null_ebitda_is_not_a_stop():
    """ИП without reporting: ebitda = null — the metric is just not computed."""
    assert codes(build_input(company("ip", 36), SNAPSHOTS["coffee_shop"], checks(), ON_DATE)) == []


def test_c4_current_overdue_31(edge_case):
    inp, _ = edge_case("e_overdue_30_31")
    (stop,) = stop_factors(inp)
    assert stop.code == "С4"
    assert (stop.reason.value, stop.reason.threshold) == (31, 30)
    assert stop.reason.message == "Сейчас есть просрочка по кредиту больше 30 дней"
    with pytest.raises(ValueError, match="С4"):
        score(inp)


def test_c4_is_not_checked_when_bki_is_unavailable():
    inp = build_input(company("ip", 36), SNAPSHOTS["coffee_shop"], checks(bki=UNAVAILABLE), ON_DATE)
    assert codes(inp) == []


def test_c5_five_months(edge_case):
    inp, expected = edge_case("e_age_edges_5")
    (stop,) = stop_factors(inp)
    assert stop.code == "С5"
    assert stop.reason.value == 5
    assert stop.improvement == (
        "Подайте заявку снова, когда бизнесу исполнится 6 мес (сейчас 5 мес)"
    )
    assert expected["outcome"] == "declined"
    with pytest.raises(ValueError, match="С5"):
        score(inp)


def test_c5_boundary_by_day():
    registered = {"legal_form": "ip", "registry_status": "active", "registered_at": "2026-04-02"}
    snapshot = SNAPSHOTS["coffee_shop"]
    assert codes(build_input(registered, snapshot, checks(), date(2026, 10, 1))) == ["С5"]
    assert codes(build_input(registered, snapshot, checks(), date(2026, 10, 2))) == []


def test_all_stop_factors_together_in_order():
    inp = build_input(
        company("ooo", 3, "liquidating"),
        {**SNAPSHOTS["retail_supplier"], "ebitda": "0"},
        checks(egrul={"status": "failed", "data": {}}, bki=bki(45, 45)),
        ON_DATE,
    )
    assert codes(inp) == ["С1", "С2", "С3", "С4", "С5"]
