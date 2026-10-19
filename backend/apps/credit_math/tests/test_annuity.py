from decimal import Decimal

import pytest

from apps.credit_math import annuity_payment, annuity_schedule, annuity_summary

D = Decimal


def test_card_example_payment():
    # docs/knowledge/credit.md: 1 000 000 ₽, 24%, 12 мес → 94 559,60 ₽/мес
    assert annuity_payment(D("1000000"), D("0.24"), 12) == D("94559.60")


def test_card_example_overpayment_is_about_134715():
    summary = annuity_summary(D("1000000"), D("0.24"), 12)

    assert summary.payment == D("94559.60")
    assert abs(summary.overpayment - D("134715")) < D("1")
    assert summary.total_paid == D("1000000.00") + summary.overpayment


@pytest.mark.parametrize(
    ("principal", "rate", "months"),
    [
        ("1000000", "0.24", 12),
        ("2009314", "0.24", 12),
        ("777777.77", "0.199", 37),
        ("5000000", "0.155", 60),
        ("100", "0.36", 3),
        ("123456.78", "0", 7),
    ],
)
def test_schedule_repays_debt_exactly(principal, rate, months):
    schedule = annuity_schedule(D(principal), D(rate), months)
    payment = annuity_payment(D(principal), D(rate), months)
    r = D(rate) / 12

    assert len(schedule) == months
    assert sum(row.principal for row in schedule) == D(principal)
    assert schedule[-1].balance == 0
    previous_balance = D(principal)
    for row in schedule:
        # interest is charged on the outstanding balance
        assert row.interest == (previous_balance * r).quantize(D("0.01"))
        assert row.payment == row.interest + row.principal
        previous_balance = row.balance
    for row in schedule[:-1]:
        assert row.payment == payment
    # the last payment only absorbs a kopeck-level remainder
    assert abs(schedule[-1].payment - payment) <= D("0.01") * months


def test_zero_rate_is_plain_division():
    assert annuity_payment(D("120000"), D("0"), 12) == D("10000.00")
    schedule = annuity_schedule(D("100"), D("0"), 3)
    assert [row.payment for row in schedule] == [D("33.33"), D("33.33"), D("33.34")]
    assert all(row.interest == 0 for row in schedule)


def test_payment_rounds_half_up_to_kopecks():
    payment = annuity_payment(D("1000000"), D("0.24"), 12)
    assert payment.as_tuple().exponent == -2


@pytest.mark.parametrize("bad", [1000000.0, True])
def test_float_and_bool_are_rejected(bad):
    with pytest.raises(TypeError):
        annuity_payment(bad, D("0.24"), 12)


@pytest.mark.parametrize(
    ("principal", "rate", "months"),
    [("-1", "0.24", 12), ("1000", "-0.01", 12), ("1000", "0.24", 0)],
)
def test_invalid_inputs_raise(principal, rate, months):
    with pytest.raises(ValueError):
        annuity_payment(D(principal), D(rate), months)
