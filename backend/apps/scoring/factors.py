"""The seven factors of the scorecard (decision-model.md §4), one function each.

Each returns a Factor: value, points, whether it passed its threshold, the client text (§7) and
the «what to improve» texts. Stop-factor inputs (age < 6, current overdue > 30, EBITDA ≤ 0) are
not scored: `score()` refuses them before any factor is called, the factors refuse them too.
"""

from dataclasses import dataclass
from decimal import Decimal

from apps.credit_math import Reason, debt_to_ebitda, dscr, to_decimal
from apps.scoring import texts
from apps.scoring.age import business_age_months
from apps.scoring.inputs import CheckResult, ScoringInput
from apps.scoring.policy import Scorecard


@dataclass(frozen=True)
class Factor:
    name: str
    value: Decimal | int | None
    points: int
    max_points: int
    passed: bool
    threshold: Decimal | None
    message: str
    missing_key: bool = False  # a key metric that could not be computed (rule П5)
    improvements: tuple[str, ...] = ()

    @property
    def lost_points(self) -> int:
        return self.max_points - self.points

    def payload(self) -> dict:
        """ScoreFactor of docs/openapi.yaml: name, value, points, message — nothing else."""
        return {
            "name": self.name,
            "value": None if self.value is None else str(self.value),
            "points": self.points,
            "message": self.message,
        }

    def as_reason(self) -> Reason:
        value = None if self.value is None else Decimal(self.value)
        return Reason(self.name, value, self.threshold, self.passed, self.message)


def business_age_factor(inp: ScoringInput, card: Scorecard) -> Factor:
    rule = card.business_age_months
    threshold = rule.passed_threshold
    max_points = rule.scale.max_points
    if inp.registered_at is None:
        return Factor(
            "business_age_months", None, rule.unknown_points, max_points, False, threshold,
            texts.NO_REGISTRATION_DATE,
        )  # fmt: skip
    age = business_age_months(inp.registered_at, inp.on_date)
    passed = rule.passed(Decimal(age))
    if passed:
        message, improvements = f"Бизнесу {age} мес — достаточно", ()
    else:
        message = f"Бизнесу {age} мес, а продукт требует от {texts.number(threshold)}"
        improvements = (f"Вернитесь через {texts.number(threshold - age)} мес",)
    return Factor(
        "business_age_months", age, rule.scale.points(Decimal(age)), max_points, passed,
        threshold, message, improvements=improvements,
    )  # fmt: skip


def dscr_factor(inp: ScoringInput, card: Scorecard, min_dscr: Decimal | None = None) -> Factor:
    """DSCR by current debts only, without the new loan: the amount is not the borrower's risk."""
    rule = card.dscr
    threshold = rule.passed_threshold if min_dscr is None else min_dscr
    max_points = rule.scale.max_points
    cfads, service = inp.metric("cfads"), inp.metric("debt_service")
    if cfads is None or service is None:
        return Factor(
            "dscr", None, rule.unknown_points, max_points, False, threshold,
            texts.MISSING_KEY_METRIC, missing_key=True,
        )  # fmt: skip
    if service == 0:
        if cfads > 0:
            return Factor("dscr", None, rule.no_debt_points, max_points, True, threshold,
                          texts.NO_DEBT)  # fmt: skip
        return Factor(
            "dscr", None, rule.scale.floor, max_points, False, threshold,
            texts.NO_DEBT_NO_CASH_FLOW, improvements=(texts.IMPROVE_DSCR,),
        )  # fmt: skip
    value = dscr(cfads, service).value
    passed = value >= threshold
    if passed:
        message = (
            f"На каждый рубль платежей по долгам приходится {texts.number(value)} ₽ свободных денег"
        )
        improvements = ()
    else:
        message = (
            f"Свободных денег на платежи по долгам мало: {texts.number(value)} ₽ на рубль "
            f"при норме {texts.number(threshold)}"
        )
        improvements = (texts.IMPROVE_DSCR,)
    return Factor(
        "dscr", value, rule.scale.points(value), max_points, passed, threshold, message,
        improvements=improvements,
    )  # fmt: skip


def debt_to_ebitda_factor(inp: ScoringInput, card: Scorecard) -> Factor:
    rule = card.debt_to_ebitda
    threshold = rule.passed_threshold
    max_points = rule.scale.max_points
    debt, ebitda = inp.metric("debt"), inp.metric("ebitda")
    if debt is None or ebitda is None:
        return Factor(
            "debt_to_ebitda", None, rule.unknown_points, max_points, False, threshold,
            texts.NO_REPORTING,
        )  # fmt: skip
    cash = inp.metric("cash")
    result = debt_to_ebitda(debt, ebitda, Decimal(0) if cash is None else cash)
    if result.value is None:
        raise ValueError(f"EBITDA ≤ 0 is stop factor С3, not a score: {result.note}")
    value = result.value
    passed = rule.passed(value)
    norm = texts.number(threshold)
    if passed:
        message = f"Долги — {texts.number(value)} годовых прибыли, норма до {norm}"
        improvements = ()
    else:
        message = f"Долги — {texts.number(value)} годовых прибыли, это больше нормы {norm}"
        improvements = (f"Снизьте долг до {norm} годовой прибыли (EBITDA)",)
    return Factor(
        "debt_to_ebitda", value, rule.scale.points(value), max_points, passed, threshold,
        message, improvements=improvements,
    )  # fmt: skip


def revenue_trend_factor(inp: ScoringInput, card: Scorecard) -> Factor:
    rule = card.revenue_trend
    threshold = rule.passed_threshold
    max_points = rule.scale.max_points
    value = inp.metric("revenue_trend")
    if value is None:
        return Factor(
            "revenue_trend", None, rule.unknown_points, max_points, False, threshold,
            texts.MISSING_KEY_METRIC, missing_key=True,
        )  # fmt: skip
    passed = rule.passed(value)
    change = value - 1
    if passed:
        sign = "+" if change > 0 else ""
        message = f"Выручка за 3 мес — {sign}{texts.percent(change)} к тем же месяцам прошлого года"
        improvements = ()
    else:
        message = f"Выручка упала на {texts.percent(-change)} к прошлому году"
        improvements = (texts.IMPROVE_TREND,)
    return Factor(
        "revenue_trend", value, rule.scale.points(value), max_points, passed, threshold,
        message, improvements=improvements,
    )  # fmt: skip


def counterparty_concentration_factor(inp: ScoringInput, card: Scorecard) -> Factor:
    rule = card.counterparty_concentration
    threshold = rule.passed_threshold
    max_points = rule.scale.max_points
    value = inp.metric("counterparty_concentration")
    if value is None:
        return Factor(
            "counterparty_concentration", None, rule.unknown_points, max_points, False,
            threshold, texts.MISSING_KEY_METRIC, missing_key=True,
        )  # fmt: skip
    passed = rule.passed(value)
    share = texts.percent(value)
    if passed:
        message, improvements = f"Крупнейший покупатель приносит {share} поступлений", ()
    else:
        message = (
            f"{share} денег приходит от одного покупателя: если он уйдёт, "
            "бизнес останется без выручки"
        )
        improvements = (
            f"Снизьте долю крупнейшего покупателя до {texts.percent(threshold)} и меньше",
        )
    return Factor(
        "counterparty_concentration", value, rule.scale.points(value), max_points, passed,
        threshold, message, improvements=improvements,
    )  # fmt: skip


def _required(check: CheckResult | None, source: str) -> CheckResult:
    if check is None:
        raise ValueError(f"scoring needs the {source} check")
    return check


def bki_history_factor(inp: ScoringInput, card: Scorecard) -> Factor:
    rule = card.bki_history
    threshold = Decimal(rule.past_short_max_days)
    check = _required(inp.check("bki"), "bki")
    if check.is_unavailable:
        return Factor("bki_history", None, rule.unknown_points, rule.max_points, False,
                      threshold, texts.BKI_UNAVAILABLE)  # fmt: skip
    current = int(check.data["current_overdue_days"])
    past = int(check.data["past_overdue_max_days"])
    if current > rule.current_max_days:
        raise ValueError("current overdue over the limit is stop factor С4, not a score")
    if current > 0:
        return Factor(
            "bki_history", past, rule.current_points, rule.max_points, False, threshold,
            f"Сейчас есть просрочка по кредиту: {texts.days(current)}",
            improvements=(texts.IMPROVE_CURRENT_OVERDUE,),
        )  # fmt: skip
    if past == 0:
        points = rule.clean_points
    elif past <= rule.past_short_max_days:
        points = rule.past_short_points
    else:
        points = rule.past_long_points
    passed = past <= rule.past_short_max_days
    if passed:
        message, improvements = texts.BKI_CLEAN, ()
    else:
        message = f"В кредитной истории была просрочка {texts.days(past)}"
        improvements = (texts.IMPROVE_PAST_OVERDUE,)
    return Factor(
        "bki_history", past, points, rule.max_points, passed, threshold, message,
        improvements=improvements,
    )  # fmt: skip


def transparent_business_factor(inp: ScoringInput, card: Scorecard) -> Factor:
    rule = card.transparent_business
    check = _required(inp.check("transparent_business"), "transparent_business")
    if check.is_unavailable:
        return Factor("transparent_business", None, rule.unknown_points, rule.max_points, False,
                      None, texts.TRANSPARENT_BUSINESS_UNAVAILABLE)  # fmt: skip
    mass_address = bool(check.data["mass_address"])
    mass_director = bool(check.data["mass_director"])
    arrears = to_decimal(check.data["tax_arrears"], "tax_arrears")
    if arrears > 0 or (mass_address and mass_director):
        points = rule.severe_points
    elif mass_address or mass_director:
        points = rule.one_flag_points
    else:
        return Factor("transparent_business", None, rule.clean_points, rule.max_points, True,
                      None, texts.TRANSPARENT_BUSINESS_CLEAN)  # fmt: skip
    findings, improvements = [], []
    if mass_address:
        findings.append("массовый адрес")
        improvements.append(texts.IMPROVE_MASS_ADDRESS)
    if mass_director:
        findings.append("массовый руководитель")
    if arrears > 0:
        findings.append(f"налоговый долг {texts.rubles(arrears)}")
        improvements.insert(0, texts.IMPROVE_TAX_ARREARS)
    return Factor(
        "transparent_business", None, points, rule.max_points, False, None,
        "ФНС: " + ", ".join(findings), improvements=tuple(improvements),
    )  # fmt: skip
