from datetime import date
from decimal import Decimal

import pytest

from apps.credit_math.statement import monthly_totals, statement_metrics, statement_months

D = Decimal
AS_OF = date(2026, 10, 1)


def tx(day: str, category: str, amount: str, *, direction: str | None = None, inn=None) -> dict:
    debit = {"payroll", "rent", "supplier", "tax", "loan_payment"}
    return {
        "date": day,
        "direction": direction or ("debit" if category in debit else "credit"),
        "amount": amount,
        "category": category,
        "counterparty_inn": inn,
    }


def months_back(count: int) -> list[str]:
    return list(statement_months(date(2025, 4, 1), AS_OF))[-count:]


# docs/data-spec.md §9.2, persona 1: M(t), O(t) in thousands of rubles, K = 10 % payer.
PERSONA_1_M = [2863, 2990, 3060, 3130, 3114, 2980, 2902, 2825, 2926, 2730, 2681, 2902,
               3004, 3136, "3208.8", 3287, 3269, "3129.2"]  # fmt: skip
PERSONA_1_O = [2434, 2542, 2601, 2661, 2647, 2533, 2467, 2401, 2487, 2321, 2279, 2467,
               2553, 2666, 2727, 2794, 2779, 2659]  # fmt: skip


def persona_1_transactions() -> list[dict]:
    txs = []
    window_kappa = D("0.10")
    months = months_back(18)
    k_values = [(D(str(m)) * 1000 * window_kappa).quantize(D(1)) for m in PERSONA_1_M]
    k_values[-1] = window_kappa * 36_000_000 - sum(k_values[6:17])
    for month, m, o, k in zip(months, PERSONA_1_M, PERSONA_1_O, k_values, strict=True):
        inflow = D(str(m)) * 1000
        txs.append(tx(f"{month}-10", "revenue", str(k), inn="0002000013"))
        txs.append(tx(f"{month}-11", "revenue", str(inflow - k)))
        txs.append(tx(f"{month}-05", "payroll", str(o * 1000)))
        txs.append(tx(f"{month}-07", "own_transfer", "50000", direction="credit"))
        txs.append(tx(f"{month}-08", "refund", "1000"))
    return txs


def test_persona_1_snapshot_to_the_kopeck():
    result = statement_metrics(persona_1_transactions(), AS_OF)
    assert len(result.months) == 18 and result.window[0] == "2025-10"
    assert result.cleaned_credit_turnover.value == D("3000000.00")
    assert result.cfads.value == D("450000.00")
    assert result.debt_service.value == D("0.00")
    assert result.counterparty_concentration.value == D("0.1000")
    assert result.revenue_trend.value == D("1.0500")
    assert result.revenue_trend.note is None


def test_excluded_categories_do_not_change_metrics():
    base = [tx("2026-09-10", "revenue", "1000"), tx("2026-09-11", "payroll", "400")]
    noise = [
        tx("2026-09-12", "own_transfer", "999", direction="credit"),
        tx("2026-09-12", "own_transfer", "999", direction="debit"),
        tx("2026-09-13", "loan", "50000"),
        tx("2026-09-14", "refund", "10"),
    ]
    clean = statement_metrics(base, AS_OF)
    noisy = statement_metrics(base + noise, AS_OF)
    assert clean == noisy
    assert clean.cfads.value == D("600.00")


def test_debt_service_and_retail_without_payer():
    txs = [
        tx("2026-09-01", "revenue", "900.00"),
        tx("2026-09-02", "revenue", "100.00", inn="0002000013"),
        tx("2026-09-15", "loan_payment", "250.00"),
    ]
    result = statement_metrics(txs, AS_OF)
    assert result.debt_service.value == D("250.00")
    assert result.counterparty_concentration.value == D("0.1000")


def test_only_retail_gives_zero_concentration():
    result = statement_metrics([tx("2026-09-01", "revenue", "500")], AS_OF)
    assert result.counterparty_concentration.value == D("0.0000")


def test_window_is_last_12_months_and_rounds_half_up():
    txs = [tx(f"{m}-03", "revenue", "1000") for m in months_back(18)]
    txs.append(tx("2026-09-04", "revenue", "0.06"))  # +0.005 per month → rounds up
    result = statement_metrics(txs, AS_OF)
    assert result.window == tuple(months_back(12))
    assert result.cleaned_credit_turnover.value == D("1000.01")


def test_short_history_trend_falls_back_with_note():
    months = months_back(9)
    amounts = ["100", "100", "100", "100", "100", "100", "90", "90", "90"]
    txs = [tx(f"{m}-03", "revenue", a) for m, a in zip(months, amounts, strict=True)]
    result = statement_metrics(txs, AS_OF, period_from=date(2026, 1, 1))
    assert len(result.window) == 9
    assert result.revenue_trend.value == D("0.9000")
    assert result.revenue_trend.note is not None


def test_history_shorter_than_6_months_has_no_trend():
    txs = [tx(f"{m}-03", "revenue", "100") for m in months_back(5)]
    result = statement_metrics(txs, AS_OF)
    assert result.revenue_trend.value is None
    assert "6 месяцев" in result.revenue_trend.note


def test_period_from_counts_empty_months():
    txs = [tx("2026-09-03", "revenue", "1200")]
    result = statement_metrics(txs, AS_OF, period_from=date(2026, 7, 1))
    assert result.months == ("2026-07", "2026-08", "2026-09")
    assert result.cleaned_credit_turnover.value == D("400.00")


def test_no_transactions_is_unavailable_not_zero():
    result = statement_metrics([], AS_OF)
    assert result.cfads.value is None and result.cfads.note
    assert result.counterparty_concentration.value is None


def test_monthly_totals():
    totals = monthly_totals(persona_1_transactions(), months_back(18))
    assert totals["2026-09"].inflow == D("3129200")
    assert totals["2026-09"].opex == D("2659000")


@pytest.mark.parametrize(
    "bad",
    [
        tx("2026-09-01", "revenue", "1", direction="debit"),
        tx("2026-09-01", "refund", "1", direction="debit"),
        tx("2026-09-01", "salary", "1", direction="debit"),
        tx("2026-09-01", "revenue", "0"),
        tx("2026-10-01", "revenue", "1"),  # not a full month before as_of
    ],
)
def test_rejects_bad_transactions(bad):
    with pytest.raises(ValueError):
        statement_metrics([tx("2026-08-01", "revenue", "1"), bad], AS_OF)


def test_rejects_float_amount():
    with pytest.raises(TypeError):
        statement_metrics([tx("2026-09-01", "revenue", 1.5)], AS_OF)
