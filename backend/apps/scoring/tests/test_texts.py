"""Client texts of decision-model.md §7 and their number formatting."""

from decimal import Decimal

import pytest

from apps.scoring import build_input, score
from apps.scoring.tests.conftest import OK_TB, ON_DATE, UNAVAILABLE, bki, checks, company
from apps.scoring.tests.d4 import SNAPSHOTS, table_input
from apps.scoring.texts import days, number, percent, rubles

D = Decimal


@pytest.mark.parametrize(
    ("value", "text"),
    [(D("2.2000"), "2,2"), (D("1.2500"), "1,25"), (D("3.0000"), "3"), (D("-0.05"), "−0,05")],
)
def test_number(value, text):
    assert number(value) == text


def test_percent_and_rubles():
    assert percent(D("0.6000")) == "60%"
    assert rubles(D("50000.00")) == "50 000 ₽"
    assert rubles(D("1234.5")) == "1 234,50 ₽"


@pytest.mark.parametrize(
    ("count", "text"),
    [(1, "1 день"), (2, "2 дня"), (5, "5 дней"), (11, "11 дней"), (21, "21 день"), (31, "31 день")],
)
def test_days(count, text):
    assert days(count) == text


def test_persona_5_messages():
    messages = {f.name: f.message for f in score(table_input("dependent_supplier")).factors}
    assert messages["dscr"] == (
        "На каждый рубль платежей по долгам приходится только 1,1 ₽ свободных денег, "
        "а нужно не меньше 1,25 ₽"
    )
    assert messages["debt_to_ebitda"] == (
        "Долг равен 4,2 годовой прибыли (EBITDA), а норма — не больше 3,5"
    )
    assert messages["revenue_trend"] == (
        "За последние 3 месяца выручка упала на 20% к тем же месяцам прошлого года"
    )
    assert messages["counterparty_concentration"].startswith("80% денег приносит один покупатель")


def test_persona_7_bki_unavailable_message():
    factor = score(table_input("bki_outage")).factor("bki_history")
    assert (
        factor.message
        == "Бюро кредитных историй не ответило, поэтому историю проверит сотрудник банка"
    )


def test_missing_metric_message():
    snapshot = {**SNAPSHOTS["coffee_shop"], "revenue_trend": None}
    factor = score(build_input(company("ip", 36), snapshot, checks(), ON_DATE)).factor(
        "revenue_trend"
    )
    assert (factor.value, factor.passed, factor.missing_key) == (None, False, True)
    assert "По счёту не хватает данных" in factor.message


def test_transparent_business_findings_and_improvements():
    data = {**OK_TB["data"], "mass_address": True, "tax_arrears": "20000.00"}
    inp = build_input(
        company("ooo", 72), SNAPSHOTS["retail_supplier"],
        checks(transparent_business={"status": "warning", "data": data}), ON_DATE,
    )  # fmt: skip
    factor = score(inp).factor("transparent_business")
    assert factor.message == "ФНС отмечает: адрес массовой регистрации, налоговый долг 20 000 ₽"
    assert factor.improvements == (
        "Погасите долг по налогам",
        "Подтвердите, что компания действительно работает по этому адресу",
    )


def test_transparent_business_unavailable_gives_two_points():
    inp = build_input(
        company("ip", 36), SNAPSHOTS["coffee_shop"], checks(transparent_business=UNAVAILABLE),
        ON_DATE,
    )  # fmt: skip
    factor = score(inp).factor("transparent_business")
    assert (factor.points, factor.passed) == (2, False)


def test_current_overdue_message():
    inp = build_input(company("ip", 36), SNAPSHOTS["coffee_shop"], checks(bki=bki(3, 3)), ON_DATE)
    factor = score(inp).factor("bki_history")
    assert factor.message == "Сейчас есть просрочка по кредиту: 3 дня"
    assert factor.improvements == ("Погасите текущую просрочку",)


def test_no_debt_without_cash_flow_is_not_passed():
    snapshot = {**SNAPSHOTS["coffee_shop"], "cfads": "-1000.00"}
    factor = score(build_input(company("ip", 36), snapshot, checks(), ON_DATE)).factor("dscr")
    assert (factor.value, factor.points, factor.passed, factor.missing_key) == (
        None, 0, False, False,
    )  # fmt: skip


def test_min_dscr_of_the_product_sets_the_dscr_pass_threshold():
    inp = table_input("furniture_maker")  # DSCR 1.8
    assert score(inp).factor("dscr").passed
    strict = score(inp, min_dscr=D("2.0")).factor("dscr")
    assert (strict.passed, strict.points, strict.threshold) == (False, 18, D("2.0"))


def test_as_reason():
    reason = score(table_input("retail_supplier")).factor("dscr").as_reason()
    assert reason.as_dict() == {
        "metric": "dscr", "value": D("2.2000"), "threshold": D("1.25"), "passed": True,
        "message": "На каждый рубль платежей по долгам приходится 2,2 ₽ свободных денег",
    }  # fmt: skip
