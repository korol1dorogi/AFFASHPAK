from decimal import Decimal

import pytest

from apps.credit_math import (
    annuity_payment,
    dscr,
    factoring_advance,
    factoring_commission,
    max_loan_by_dscr,
    max_payment_by_dscr,
    overdraft_limit,
)
from apps.credit_math.annuity import annuity_payment_exact

D = Decimal


def test_card_example_max_loan_by_dscr():
    # 300 000/1.25 − 50 000 = 190 000 ₽/мес; 24%, 12 мес → P_max = 2 009 314 ₽
    assert max_payment_by_dscr(D("300000"), D("50000")) == D("190000")
    result = max_loan_by_dscr(D("300000"), D("50000"), D("0.24"), 12)
    assert result.value == D("2009314.00")


@pytest.mark.parametrize("cfads", ["300000", "123456.78", "1000000", "87000.01", "250000"])
@pytest.mark.parametrize("current", ["0", "50000", "13333.33"])
@pytest.mark.parametrize("rate", ["0", "0.12", "0.24", "0.299"])
@pytest.mark.parametrize("months", [1, 12, 36, 120, 360])
@pytest.mark.parametrize("min_dscr", ["1.25", "1.3", "1.1"])
def test_dscr_holds_after_all_roundings(cfads, current, rate, months, min_dscr):
    result = max_loan_by_dscr(D(cfads), D(current), D(rate), months, D(min_dscr))
    a_max = max_payment_by_dscr(D(cfads), D(current), D(min_dscr))
    if a_max <= 0:
        assert result.value is None
        return

    p_max = result.value
    payment = annuity_payment(p_max, D(rate), months)
    assert payment <= a_max
    # independent check with the rounded payment
    assert dscr(D(cfads), D(current) + payment).value >= D(min_dscr)
    # rounded down to whole rubles and maximal: one more ruble would not fit
    assert p_max == p_max.to_integral_value()
    next_ruble = p_max + 1
    assert (
        annuity_payment_exact(next_ruble, D(rate), months) > a_max
        or annuity_payment(next_ruble, D(rate), months) > a_max
    )


def test_max_loan_is_maximal_for_card_example():
    p_max = max_loan_by_dscr(D("300000"), D("50000"), D("0.24"), 12).value
    assert annuity_payment(p_max + 1, D("0.24"), 12) > D("190000")


def test_no_free_cash_flow_means_no_loan():
    result = max_loan_by_dscr(D("100000"), D("80000"), D("0.24"), 12)
    assert result.value is None
    assert result.note


def test_negative_cfads_means_no_loan():
    assert max_loan_by_dscr(D("-1"), D("0"), D("0.24"), 12).value is None


def test_card_example_overdraft_limit():
    assert overdraft_limit(D("3000000"), D("0.3")) == D("900000.00")


def test_card_example_factoring_advance():
    assert factoring_advance(D("5000000"), D("0.9")) == D("4500000.00")


@pytest.mark.parametrize("share", ["0", "1.01", "-0.1"])
def test_shares_must_be_in_range(share):
    with pytest.raises(ValueError):
        overdraft_limit(D("1000"), D(share))
    with pytest.raises(ValueError):
        factoring_advance(D("1000"), D(share))


# --- Factoring commission (decision-model.md §5, persona 2) ---


def test_persona_2_factoring_commission():
    assert factoring_commission(D("5000000"), D("0.005")) == D("25000.00")


def test_factoring_commission_rounds_half_up_to_kopecks():
    assert factoring_commission(D("1001"), D("0.005")) == D("5.01")  # 5.005 → 5.01
    assert factoring_commission(D("0"), D("0.005")) == D("0.00")


@pytest.mark.parametrize(("amount", "commission"), [("-1", "0.005"), ("100", "-0.1"), ("100", "1")])
def test_factoring_commission_rejects_bad_inputs(amount, commission):
    with pytest.raises(ValueError):
        factoring_commission(D(amount), D(commission))


def test_factoring_commission_rejects_float():
    with pytest.raises(TypeError):
        factoring_commission(D("5000000"), 0.005)
