"""Personas reproduce the numbers of docs/knowledge/credit.md and docs/demo.md via credit_math.

Product parameters (alpha 0.3, beta 0.9, 24% for 12 months) are the examples from those docs;
they belong to the catalog (D3), not to the generated data.
"""

from decimal import Decimal

import pytest

from apps.credit_math import (
    ccc,
    counterparty_concentration,
    factoring_advance,
    max_loan_by_dscr,
    overdraft_limit,
    revenue_trend,
    working_capital_need,
)

D = Decimal


@pytest.fixture(scope="module")
def personas(dataset) -> dict[str, dict]:
    return {persona["code"]: persona for persona in dataset["personas"]}


def figures(personas, code: str) -> dict:
    return personas[code]["figures"]


def test_persona_set_and_companies(dataset, personas):
    assert [p["scenario"] for p in dataset["personas"]] == [1, 2, 3, 5]
    companies = {company["inn"]: company for company in dataset["companies"]}
    for persona in personas.values():
        company = companies[persona["company_inn"]]
        assert company["registry_status"] == "active"
        assert "(демо)" in persona["title"]
    assert companies[personas["coffee_shop"]["company_inn"]]["legal_form"] == "ip"
    assert companies[personas["garden_store"]["company_inn"]]["legal_form"] == "ip"
    assert companies[personas["retail_supplier"]["company_inn"]]["legal_form"] == "ooo"
    assert companies[personas["dependent_supplier"]["company_inn"]]["legal_form"] == "ooo"


def test_coffee_shop_overdraft_900k(personas):
    f = figures(personas, "coffee_shop")
    assert personas["coffee_shop"]["need_type"] == "cash_gap"
    assert overdraft_limit(f["cleaned_credit_turnover"], D("0.3")) == D("900000.00")


def test_retail_supplier_factoring_4_5m(personas):
    f = figures(personas, "retail_supplier")
    assert personas["retail_supplier"]["need_type"] == "receivable_delay"
    assert factoring_advance(f["invoice_amount"], D("0.9")) == D("4500000.00")


def test_garden_store_need_5_3m_but_dscr_allows_2_009_314(personas):
    f = figures(personas, "garden_store")
    assert personas["garden_store"]["need_type"] == "working_capital"
    cycle = ccc(f["revenue"], f["cogs"], f["receivables"], f["inventory"], f["payables"])
    assert (cycle.dso.value, cycle.dio.value, cycle.dpo.value) == (D(45), D(30), D(20))
    assert cycle.ccc.value == D(55)

    need = working_capital_need(f["receivables"], f["inventory"], f["payables"])
    assert need == D("5300000.00") == D(f["requested_amount"])

    cap = max_loan_by_dscr(f["cfads"], f["debt_service"], D("0.24"), f["term_months"])
    assert cap.value == D("2009314.00")
    assert cap.value < need  # the counteroffer case: DSCR, not the need, limits the amount


def test_dependent_supplier_concentration_and_trend_0_8(personas):
    f = figures(personas, "dependent_supplier")
    assert counterparty_concentration(f["top_inflow"], f["total_inflow"]).value == D("0.8")
    trend = revenue_trend(f["current_avg"], f["base_avg"])
    assert trend.value == D("0.8")
    assert trend.note is None  # year over year, seasonality excluded


@pytest.mark.skip(reason="D5 apps/scoring ещё нет: грейды A–E считать нечем (S2 → D9)")
def test_grade_distribution_in_corridor():
    """A ~15%, B ~30%, C ~25%, D ~15%, E ~10%, stop factors ~5% (docs/plan.md)."""
