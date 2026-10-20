"""Edge cases of docs/data-spec.md §10: built through the statement, checked by credit_math."""

from datetime import date
from decimal import Decimal

import pytest

from apps.credit_math import debt_to_ebitda, max_loan_by_dscr
from apps.credit_math.statement import statement_metrics
from apps.demo_data.amounts import add_months
from apps.demo_data.edge_cases import EDGES
from apps.demo_data.ids import is_valid_inn, is_valid_ogrn

D = Decimal
AS_OF = date(2026, 10, 1)


@pytest.fixture(scope="module")
def edges(dataset) -> dict[str, dict]:
    return {edge["code"]: edge for edge in dataset["edge_cases"]}


def months(edge) -> int:
    return len(statement_metrics(edge["statement"]["transactions"], AS_OF,
                                 period_from=date.fromisoformat(edge["statement"]["period_from"])
                                 ).months)  # fmt: skip


def test_codes_and_order(dataset):
    assert [e["code"] for e in dataset["edge_cases"]] == [e.code for e in EDGES]
    assert "e_score_90_60_50" not in {e.code for e in EDGES}  # inputs not given by §10


def test_edge_companies_are_not_seeded(dataset):
    keys = {c["_key"] for c in dataset["companies"]}
    for edge in dataset["edge_cases"]:
        assert edge["company"]["_key"] == f"edge_{edge['code']}"
        assert edge["company"]["_key"] not in keys


def test_edge_numbers_100_and_up(dataset):
    numbers = {"ip": [], "ooo": []}
    for edge in dataset["edge_cases"]:
        company = edge["company"]
        assert is_valid_inn(company["inn"]) and is_valid_ogrn(company["ogrn"])
        inn = company["inn"]
        numbers[company["legal_form"]].append(int(inn[4:9] if len(inn) == 10 else inn[4:10]))
    for values in numbers.values():
        assert values == list(range(100, 100 + len(values)))


def test_snapshot_comes_from_the_statement(dataset):
    for edge in dataset["edge_cases"]:
        if edge["statement"] is None:
            assert edge["snapshot"] is None and edge["code"] == "e_all_unavailable"
            continue
        statement, snapshot = edge["statement"], edge["snapshot"]
        metrics = statement_metrics(
            statement["transactions"], AS_OF,
            period_from=date.fromisoformat(statement["period_from"]),
        )  # fmt: skip
        for field in ("cleaned_credit_turnover", "cfads", "debt_service"):
            assert str(getattr(metrics, field).value) == snapshot[field], (edge["code"], field)
        for field in ("counterparty_concentration", "revenue_trend"):
            value = getattr(metrics, field).value
            got = None if value is None else str(value)
            if edge["code"] == "g4":  # §10: null metrics are given directly as test inputs
                assert snapshot[field] is None
            else:
                assert got == snapshot[field], (edge["code"], field)


def test_differences(edges):
    assert edges["g1"]["snapshot"]["debt_service"] == "240000.00"
    assert edges["g2"]["application"]["requested_amount"] == "2009314.00"
    assert edges["g3"]["checks"]["bki"]["data"]["past_overdue_max_days"] == 10
    for code in ("g5", "g6"):
        assert edges[code]["checks"]["bki"] == {"status": "unavailable", "data": {}}
    assert edges["g5"]["checks"]["egrul"]["data"]["registry_status"] == "liquidating"
    assert edges["g8"]["snapshot"]["ebitda"] == "0.00"
    assert edges["g10"]["company"]["registered_at"] is None
    assert edges["e_ebitda_negative"]["snapshot"]["ebitda"] == "-500000.00"
    assert edges["e_no_invoice"]["application"]["invoice_amount"] is None
    assert edges["e_over_amount_max"]["application"]["requested_amount"] == "12000000.00"
    unavailable = edges["e_all_unavailable"]["checks"]
    assert {s: c["status"] for s, c in unavailable.items()} == dict.fromkeys(
        unavailable, "unavailable"
    )


def test_g7_alternative_product_amount(edges):
    """D4 Г7: leasing at 22.5 % for 36 months — 11 443 551 ₽ from the edge's own snapshot."""
    edge = edges["g7"]
    snapshot = edge["snapshot"]
    assert snapshot["revenue_trend"] == "1.0000"
    assert edge["checks"]["bki"]["data"]["past_overdue_max_days"] == 0
    assert edge["application"]["collateral_description"] is None
    assert edge["application"]["requested_amount"] == "12000000.00"
    cap = max_loan_by_dscr(D(snapshot["cfads"]), D(snapshot["debt_service"]), D("0.225"), 36)
    assert cap.value == D("11443551.00")


def test_e_de_35(edges):
    s = edges["e_de_35"]["snapshot"]
    assert debt_to_ebitda(D(s["debt"]), D(s["ebitda"]), D(s["cash"])).value == D("3.5000")


@pytest.mark.parametrize(
    ("code", "kappa"), [("030", "0.3000"), ("050", "0.5000"), ("070", "0.7000")]
)
def test_concentration_edges(edges, code, kappa):
    assert edges[f"e_conc_edges_{code}"]["snapshot"]["counterparty_concentration"] == kappa


def test_trend_090(edges):
    assert edges["e_trend_090"]["snapshot"]["revenue_trend"] == "0.9000"


@pytest.mark.parametrize(("age", "h"), [(5, 4), (6, 5), (12, 11), (24, 18), (36, 18)])
def test_age_edges(edges, age, h):
    edge = edges[f"e_age_edges_{age}"]
    assert edge["company"]["registered_at"] == add_months(AS_OF, -age).isoformat()
    assert months(edge) == h
    assert (edge["snapshot"]["revenue_trend"] is None) == (h < 6)


def test_short_history_and_young_wcl(edges):
    short = edges["e_short_history"]
    assert months(short) == 9 and short["checks"]["bank_account"]["data"]["months"] == 9
    metrics = statement_metrics(short["statement"]["transactions"], AS_OF)
    assert metrics.revenue_trend.note is not None  # previous 3 months, seasonality not excluded
    young = edges["e_young_wcl"]
    assert months(young) == 7 and young["snapshot"]["revenue_trend"] == "1.0000"
    for obligation in young["checks"]["bki"]["data"]["obligations"]:
        assert obligation["opened_at"] >= young["company"]["registered_at"]


def test_expected_only_states_the_spec(edges):
    for edge in edges.values():
        expected = edge["expected"]
        assert set(expected) == {"outcome", "grade", "total", "note"} and expected["note"]
    assert edges["g3"]["expected"] == {
        "outcome": "counteroffer",
        "grade": "B",
        "total": 75,
        "note": "D4 Г3: 75 → B, контроффер 24 %",
    }
