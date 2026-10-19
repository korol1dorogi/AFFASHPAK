from decimal import Decimal

import pytest

from apps.credit_math import (
    ccc,
    check_at_least,
    check_at_most,
    counterparty_concentration,
    debt_to_ebitda,
    dscr,
    expected_loss,
    exposure_at_default,
    revenue_trend,
    working_capital_need,
)

D = Decimal

# Seasonal garden shop from docs/knowledge/credit.md and docs/demo.md (persona 3)
REVENUE = D("36500000")
COGS = D("29200000")
RECEIVABLES = D("4500000")
INVENTORY = D("2400000")
PAYABLES = D("1600000")


# --- DSCR ---


def test_card_example_dscr():
    assert dscr(D("300000"), D("50000") + D("190000")).value == D("1.2500")


def test_dscr_without_debt_is_none_with_reason():
    result = dscr(D("300000"), D("0"))
    assert result.value is None
    assert "Долга нет" in result.note


@pytest.mark.parametrize("cfads", ["0", "-100000"])
def test_dscr_non_positive_cfads_does_not_pass(cfads):
    reason = check_at_least(
        "dscr", dscr(D(cfads), D("50000")), D("1.25"), ok="ok", fail="Поток не покрывает платежи"
    )
    assert reason.passed is False
    assert reason.value <= 0


# --- Debt/EBITDA ---


def test_card_example_debt_to_ebitda():
    assert debt_to_ebitda(D("6000000"), D("2400000")).value == D("2.5000")
    assert debt_to_ebitda(D("6000000"), D("2400000"), cash=D("600000")).value == D("2.2500")


@pytest.mark.parametrize("ebitda", ["0", "-1000000"])
def test_non_positive_ebitda_is_none_and_fails_check(ebitda):
    result = debt_to_ebitda(D("6000000"), D(ebitda))
    assert result.value is None
    reason = check_at_most("debt_to_ebitda", result, D("3.5"), ok="ok", fail="fail")
    assert reason.passed is False
    assert reason.message == result.note
    assert "стоп-фактор" in reason.message


# --- Cash conversion cycle and working capital ---


def test_card_example_ccc():
    cycle = ccc(REVENUE, COGS, RECEIVABLES, INVENTORY, PAYABLES)
    assert cycle.dso.value == D("45")
    assert cycle.dio.value == D("30")
    assert cycle.dpo.value == D("20")
    assert cycle.ccc.value == D("55")


def test_ccc_without_cogs_has_no_dio_dpo():
    cycle = ccc(REVENUE, D("0"), RECEIVABLES, D("0"), PAYABLES)
    assert cycle.dso.value == D("45")
    assert cycle.dio.value is None
    assert cycle.dpo.value is None
    assert cycle.ccc.value is None
    assert cycle.dio.note and cycle.ccc.note


def test_card_example_working_capital_need():
    assert working_capital_need(RECEIVABLES, INVENTORY, PAYABLES) == D("5300000.00")


def test_working_capital_need_identity_through_days():
    """DSO·revenue/365 + (DIO − DPO)·COGS/365 = need; CCC·revenue/365 is the trap (5.5 mln)."""
    cycle = ccc(REVENUE, COGS, RECEIVABLES, INVENTORY, PAYABLES)
    via_days = cycle.dso.value * REVENUE / 365 + (cycle.dio.value - cycle.dpo.value) * COGS / 365
    need = working_capital_need(RECEIVABLES, INVENTORY, PAYABLES)

    assert via_days == need
    trap = cycle.ccc.value * REVENUE / 365
    assert trap == D("5500000")
    assert trap != need


# --- Concentration, trend, expected loss ---


def test_card_example_counterparty_concentration():
    assert counterparty_concentration(D("2400000"), D("3000000")).value == D("0.8000")


def test_concentration_without_inflows_is_none():
    assert counterparty_concentration(D("0"), D("0")).value is None


def test_card_example_revenue_trend_year_over_year():
    result = revenue_trend(D("2400000"), D("3000000"))
    assert result.value == D("0.8000")
    assert result.note is None


def test_revenue_trend_short_history_has_note():
    result = revenue_trend(D("2400000"), D("3000000"), year_over_year=False)
    assert result.value == D("0.8000")
    assert "меньше 15 месяцев" in result.note


def test_revenue_trend_zero_base_is_none():
    assert revenue_trend(D("100"), D("0")).value is None


def test_card_example_expected_loss_and_ead():
    assert expected_loss(D("0.04"), D("0.45"), D("2000000")) == D("36000.00")
    assert exposure_at_default(D("400000"), D("1000000"), D("0.5")) == D("700000.00")


def test_reason_shape_matches_agents_md():
    reason = check_at_least("dscr", dscr(D("300000"), D("240000")), D("1.25"), ok="ok", fail="no")
    assert reason.as_dict() == {
        "metric": "dscr",
        "value": D("1.2500"),
        "threshold": D("1.25"),
        "passed": True,
        "message": "ok",
    }


def test_float_is_rejected_everywhere():
    with pytest.raises(TypeError):
        dscr(300000.0, D("1"))
    with pytest.raises(TypeError):
        working_capital_need(D("1"), 2.5, D("1"))
