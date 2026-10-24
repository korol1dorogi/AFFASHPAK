"""Client texts of decision-model.md §7 and their number formatting."""

from decimal import Decimal

import pytest

from apps.scoring import build_input, score
from apps.scoring.tests.conftest import OK_TB, ON_DATE, UNAVAILABLE, bki, checks, company
from apps.scoring.tests.d4 import SNAPSHOTS, table_input
from apps.scoring.texts import (
    age,
    age_genitive,
    days,
    months,
    months_genitive,
    number,
    percent,
    rubles,
    years,
)

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


@pytest.mark.parametrize(
    ("count", "after_na", "after_do"),
    [
        (1, "1 месяц", "1 месяца"),
        (3, "3 месяца", "3 месяцев"),
        (12, "12 месяцев", "12 месяцев"),
        (21, "21 месяц", "21 месяца"),
        (24, "24 месяца", "24 месяцев"),
    ],
)
def test_months_in_both_cases(count, after_na, after_do):
    assert months(count) == after_na  # «на 24 месяца», «через 3 месяца»
    assert months_genitive(count) == after_do  # «до 24 месяцев», «не меньше 1 месяца»


@pytest.mark.parametrize(
    ("total", "nominative", "genitive"),
    [
        (5, "5 месяцев", "5 месяцев"),
        (12, "1 год", "1 года"),
        (15, "1 год и 3 месяца", "1 года и 3 месяцев"),
        (24, "2 года", "2 лет"),
        (144, "12 лет", "12 лет"),
    ],
)
def test_business_age_in_years_and_months(total, nominative, genitive):
    assert age(total) == nominative  # «Бизнесу 1 год и 3 месяца»
    assert age_genitive(total) == genitive  # «нужно не меньше 2 лет»


@pytest.mark.parametrize(
    ("value", "accusative", "genitive"),
    [
        (D("4.2"), "4,2 года", "4,2 года"),
        (D("3.5"), "3,5 года", "3,5 года"),
        (D("1"), "1 год", "1 года"),
        (D("2"), "2 года", "2 лет"),
        (D("5.0000"), "5 лет", "5 лет"),
    ],
)
def test_years_of_profit(value, accusative, genitive):
    assert years(value) == accusative  # «прибыль за 4,2 года»
    assert years(value, genitive=True) == genitive  # «норма — не больше 2 лет»


def test_persona_5_messages():
    messages = {f.name: f.message for f in score(table_input("dependent_supplier")).factors}
    assert messages["dscr"] == (
        "На каждый рубль платежей по долгам приходится только 1,1 ₽ свободных денег, "
        "а нужно не меньше 1,25 ₽"
    )
    assert messages["debt_to_ebitda"] == (
        "Чтобы отдать долги, понадобится операционная прибыль (EBITDA) за 4,2 года, "
        "а норма — не больше 3,5 года"
    )
    assert messages["revenue_trend"] == (
        "Выручка за последние три месяца на 20% меньше, чем год назад, а допустимо не больше "
        "чем на 10%"
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
