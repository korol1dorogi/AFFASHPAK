"""Rules П3–П8 after scoring (decision-model.md §5). Stops and gaps are handled before this."""

from dataclasses import dataclass
from decimal import Decimal

from apps.applications.models import Application, DecisionOutcome
from apps.applications.offers import rate_for
from apps.credit_math import (
    annuity_payment,
    dscr,
    factoring_advance,
    factoring_commission,
    max_loan_by_dscr,
    overdraft_limit,
    working_capital_need_metric,
)
from apps.products.models import Product
from apps.scoring import ScoringInput, business_age_months, get_scorecard, review_reasons, score
from apps.scoring.inputs import SOURCES
from apps.scoring.policy import CURRENT_POLICY_VERSION, get_policy
from apps.scoring.scorecard import ScoreResult
from apps.scoring.texts import age_genitive, months, number, percent, points, rubles

# Who the client reads about when a source does not answer (decision-model.md §7).
SOURCE_NAME = {
    "egrul": "ЕГРЮЛ/ЕГРИП",
    "transparent_business": "«Прозрачный бизнес»",
    "bki": "Бюро кредитных историй",
    "bank_account": "Выписка по счёту",
}


@dataclass(frozen=True)
class Decision:
    outcome: str
    score: ScoreResult | None
    reasons: list[dict]
    improvements: list[str]
    offer: dict | None
    source_unavailable: bool
    policy_version: str


def decide(application: Application, inp: ScoringInput) -> Decision:
    policy = get_policy()
    product = application.product
    if product is None:
        raise ValueError("decision needs a product")
    result = score(inp, min_dscr=_decimal(product.params.get("min_dscr"), "1.25"))
    # No data is not a decline (SRC2): unavailable, restricted or consent_missing → an officer.
    # Only a source that did not answer raises source_unavailable (the queue's outage mark).
    no_data = [source for source in SOURCES if (check := inp.check(source)) and check.has_no_data]
    reasons = [_factor_reason(factor) for factor in result.factors]
    reasons.append(_score_reason(result))
    source_unavailable = any(inp.check(source).is_unavailable for source in no_data)
    for source in no_data:
        reasons.append(_row(f"source_{source}", None, None, False, _no_data_text(inp, source)))
    # ЕГРЮЛ marks (SRC5): unreliable address or director, pending exclusion → an officer.
    marks = review_reasons(inp)
    for mark in marks:
        reasons.append(_row(mark.metric, mark.value, mark.threshold, mark.passed, mark.message))

    def pack(
        outcome: str,
        *,
        offer: dict | None = None,
        improvements: list[str] | None = None,
        extra: list[dict] | None = None,
    ) -> Decision:
        return Decision(
            outcome=outcome,
            score=result,
            reasons=[*reasons, *(extra or [])],
            improvements=improvements or [],
            offer=offer,
            source_unavailable=source_unavailable,
            policy_version=policy.policy_version or CURRENT_POLICY_VERSION,
        )

    if no_data or marks or inp.registered_at is None:
        # The officer still gets the amount the data allows (decision-model.md §5, П3 and П5).
        _cap, extra = _size(product, application, inp, result.grade, application.term_months)
        return pack(DecisionOutcome.MANUAL_REVIEW, extra=extra)
    if result.grade == "E":
        texts: list[str] = []
        for factor in sorted(result.factors, key=lambda item: item.lost_points, reverse=True):
            texts.extend(factor.improvements)
        return pack(DecisionOutcome.DECLINED, improvements=texts)
    if _needs_officer(result, product):
        _cap, extra = _size(product, application, inp, result.grade, application.term_months)
        return pack(DecisionOutcome.MANUAL_REVIEW, extra=extra)

    chosen = product
    requirements: dict | None = None
    if not _fits(product, application, inp):
        alternative = _alternative(product, application, inp)
        requirements = _requirements_row(product, inp, alternative)
        if alternative is None:
            return pack(
                DecisionOutcome.DECLINED,
                improvements=["Для такого запроса другого подходящего продукта нет"],
                extra=[requirements],
            )
        chosen = alternative

    term = _clamp_term(chosen, application.term_months)
    rate = rate_for(chosen, result.grade)
    cap, extra = _size(chosen, application, inp, result.grade, term)
    if requirements is not None:
        extra.insert(0, requirements)  # why the product changed comes first (F9, F11)
    if cap is None:
        outcome = (
            DecisionOutcome.DECLINED if chosen is not product else DecisionOutcome.MANUAL_REVIEW
        )
        return pack(outcome, extra=extra)
    offered = min(cap, application.requested_amount)
    if offered < chosen.amount_min:
        outcome = (
            DecisionOutcome.DECLINED if chosen is not product else DecisionOutcome.MANUAL_REVIEW
        )
        return pack(outcome, extra=extra)
    if not chosen.is_revolving:
        extra.append(_dscr_after(chosen, inp, offered, rate, term))
    if chosen is not product:
        outcome = DecisionOutcome.ALTERNATIVE_PRODUCT
    elif offered < application.requested_amount:
        outcome = DecisionOutcome.COUNTEROFFER
    else:
        outcome = DecisionOutcome.OFFER
    improvements = _amount_improvements(chosen, inp, offered, application.requested_amount, rate)
    return pack(
        outcome,
        extra=extra,
        improvements=improvements,
        offer={"product": chosen, "amount": offered, "term_months": term, "rate": rate},
    )


def _needs_officer(result: ScoreResult, product: Product) -> bool:
    if result.grade in {"C", "D"}:
        return True
    if result.missing_key_metrics > get_policy().max_missing_key_metrics:
        return True
    if product.is_revolving:
        return False
    value = result.factor("debt_to_ebitda").value
    if value is None:
        return False
    limit = _decimal(product.params.get("max_debt_to_ebitda"), "3.5")
    return Decimal(str(value)) > limit


def _fits(product: Product, application: Application, inp: ScoringInput) -> bool:
    requirements = product.requirements or {}
    forms = requirements.get("legal_forms") or []
    if forms and inp.legal_form not in forms:
        return False
    if inp.registered_at is None:
        return False
    minimum = int(requirements.get("min_business_age_months") or 0)
    if business_age_months(inp.registered_at, inp.on_date) < minimum:
        return False
    described = bool((application.collateral_description or "").strip())
    return not product.collateral_required or described


def _alternative(product: Product, application: Application, inp: ScoringInput) -> Product | None:
    kind = get_policy().alternatives.get(product.kind)
    if not kind:
        return None
    candidate = Product.objects.filter(kind=kind, is_active=True).order_by("code").first()
    if candidate is None or not _fits(candidate, application, inp):
        return None
    return candidate


def _requirements_row(product: Product, inp: ScoringInput, alternative: Product | None) -> dict:
    """Why the requested product does not fit (П6): the first broken requirement, in words."""
    requirements = product.requirements or {}
    forms = requirements.get("legal_forms") or []
    minimum = int(requirements.get("min_business_age_months") or 0)
    if forms and inp.legal_form not in forms:
        cause = f"{product.name} не выдают компаниям с такой правовой формой"
    elif inp.registered_at is None:
        cause = f"{product.name}: в ЕГРЮЛ нет даты регистрации компании"
    elif business_age_months(inp.registered_at, inp.on_date) < minimum:
        cause = f"{product.name} выдают бизнесу не младше {age_genitive(minimum)}"
    else:
        cause = f"{product.name} выдают только под залог"
    tail = f", зато подходит {alternative.name.lower()}" if alternative else ""
    return _row("product_requirements", None, None, False, cause + tail)


def _clamp_term(product: Product, term: int) -> int:
    return min(max(term, product.term_min_months), product.term_max_months)


def _size(
    product: Product, application: Application, inp: ScoringInput, grade: str, term: int
) -> tuple[Decimal | None, list[dict]]:
    rate = rate_for(product, grade)
    requested = application.requested_amount
    if product.kind == "overdraft":
        return _overdraft_size(product, inp, requested)
    if product.kind == "factoring":
        return _factoring_size(product, application, requested)
    by_dscr = _dscr_cap(product, inp, rate, term)
    if by_dscr is None:  # None and a reason, never a silent gap (AGENTS.md)
        text = (
            "По счёту не хватает данных, чтобы посчитать сумму, поэтому её посчитает "
            "сотрудник банка"
        )
        return None, [_row("max_loan_by_dscr", None, requested, False, text)]
    reasons = [_dscr_reason(by_dscr, requested, rate, term)]
    limit = min(by_dscr, product.amount_max)
    if product.kind == "working_capital_loan":
        need = working_capital_need_metric(
            inp.metric("receivables"), inp.metric("inventory"), inp.metric("payables")
        )
        reasons.insert(0, _need_reason(need, requested))
        if need.value is not None:
            limit = min(limit, need.value)
    return limit, reasons


def _overdraft_size(
    product: Product, inp: ScoringInput, requested: Decimal
) -> tuple[Decimal | None, list[dict]]:
    turnover = inp.metric("cleaned_credit_turnover")
    if turnover is None:
        text = "Нет данных об оборотах по счёту, поэтому лимит посчитает сотрудник банка"
        return None, [_row("overdraft_limit", None, requested, False, text)]
    alpha = _decimal(product.params.get("alpha"), "0.3")
    limit = min(overdraft_limit(turnover, alpha), product.amount_max)
    passed = limit >= requested
    text = (
        f"Лимит — {percent(alpha)} от средних поступлений на счёт за месяц: {rubles(limit)}"
        if passed
        else f"По оборотам на счёте доступно {rubles(limit)}, это меньше запрошенного"
    )
    return limit, [_row("overdraft_limit", limit, requested, passed, text)]


def _factoring_size(
    product: Product, application: Application, requested: Decimal
) -> tuple[Decimal | None, list[dict]]:
    invoice = application.invoice_amount
    if invoice is None:
        text = "Не указана сумма отгрузки, поэтому аванс не посчитать"
        return None, [_row("factoring_advance", None, requested, False, text)]
    beta = _decimal(product.params.get("beta"), "0.9")
    limit = min(factoring_advance(invoice, beta), product.amount_max)
    passed = limit >= requested
    text = (
        f"Сразу можно получить {percent(beta)} от суммы отгрузки: {rubles(limit)}"
        if passed
        else f"Под эту отгрузку доступно {rubles(limit)}"
    )
    reasons = [_row("factoring_advance", limit, requested, passed, text)]
    commission = product.params.get("commission")
    if commission is not None:
        fee = factoring_commission(invoice, _decimal(commission, "0"))
        reasons.append(
            _row("factoring_commission", fee, None, True, f"Разовая комиссия: {rubles(fee)}")
        )
    return limit, reasons


def _dscr_cap(product: Product, inp: ScoringInput, rate: Decimal, term: int) -> Decimal | None:
    cfads, service = inp.metric("cfads"), inp.metric("debt_service")
    if cfads is None or service is None:
        return None
    metric = max_loan_by_dscr(cfads, service, rate, term, _min_dscr(product))
    if metric.value is None:
        return None
    return min(metric.value, product.amount_max)


def _dscr_reason(limit: Decimal, requested: Decimal, rate: Decimal, term: int) -> dict:
    passed = limit >= requested
    text = (
        f"Платёж бизнесу по силам: можно взять до {rubles(limit)}"
        if passed
        else (
            f"На {months(term)} под {percent(rate)} можно взять не больше {rubles(limit)}: "
            "платёж по большей сумме будет бизнесу не по силам"
        )
    )
    return _row("max_loan_by_dscr", limit, requested, passed, text)


def _need_reason(need, requested: Decimal) -> dict:
    if need.value is None:
        return _row("working_capital_need", None, requested, False, need.note or "")
    passed = need.value >= requested
    text = (
        f"Сейчас в обороте бизнеса {rubles(need.value)}, и запрошенная сумма не больше этого"
        if passed
        else f"Сейчас в обороте бизнеса {rubles(need.value)}, это меньше запрошенного"
    )
    return _row("working_capital_need", need.value, requested, passed, text)


def _dscr_after(
    product: Product, inp: ScoringInput, amount: Decimal, rate: Decimal, term: int
) -> dict:
    payment = annuity_payment(amount, rate, term)
    current = inp.metric("debt_service") or Decimal(0)
    cfads = inp.metric("cfads")
    if cfads is None:
        return _row("dscr_after", None, _min_dscr(product), False, "Нет данных о деньгах по счёту")
    metric = dscr(cfads, current + payment)
    threshold = _min_dscr(product)
    passed = metric.value is not None and metric.value >= threshold
    coverage = "нет данных" if metric.value is None else number(metric.value)
    text = (
        f"С новым платежом {rubles(payment)} в месяц свободных денег в {coverage} раза больше, "
        "чем уходит на все платежи"
    )
    return _row("dscr_after", metric.value, threshold, passed, text)


def _amount_improvements(
    product: Product, inp: ScoringInput, offered: Decimal, requested: Decimal, rate: Decimal
) -> list[str]:
    if offered >= requested or product.kind in {"overdraft", "factoring"}:
        return []
    texts = ["Снизьте платежи по текущим долгам"]
    cfads, service = inp.metric("cfads"), inp.metric("debt_service")
    if cfads is None or service is None:
        return texts
    longer = max_loan_by_dscr(cfads, service, rate, product.term_max_months, _min_dscr(product))
    if longer.value is not None:
        term = months(product.term_max_months)
        texts.insert(0, f"Если взять на {term}, можно получить до {rubles(longer.value)}")
    return texts


def _score_reason(result: ScoreResult) -> dict:
    """Passes from the lowest grade offered automatically (B, decision-model.md §6)."""
    card = get_scorecard(result.model_version)
    threshold = next(minimum for minimum, grade in card.grades if grade == "B")
    return {
        "metric": "score_total",
        "value": str(result.total),
        "threshold": str(threshold),
        "passed": result.total >= threshold,
        "message": f"{points(result.total)} из 100, это оценка {result.grade}",
    }


def _no_data_text(inp: ScoringInput, source: str) -> str:
    check = inp.check(source)
    if source == "bank_account" and check is not None and check.data.get("not_connected"):
        return "Счёт не подключён, поэтому данные по счёту проверит сотрудник банка. Это не отказ"
    if check is not None and (
        check.status == "consent_missing" or check.data.get("consent_missing")
    ):
        return (
            "Согласия на запрос в бюро нет, поэтому кредитную историю проверит сотрудник банка. "
            "Это не отказ"
        )
    if check is not None and check.status == "restricted":
        return (
            f"{SOURCE_NAME[source]}: сведения скрыты, поэтому заявку проверит сотрудник банка. "
            "Это не отказ"
        )
    return (
        f"{SOURCE_NAME[source]} сейчас не отвечает, поэтому заявку проверит сотрудник банка. "
        "Это не отказ"
    )


def _factor_reason(factor) -> dict:
    value = None if factor.value is None else str(factor.value)
    threshold = None if factor.threshold is None else str(factor.threshold)
    return {
        "metric": factor.name,
        "value": value,
        "threshold": threshold,
        "passed": factor.passed,
        "message": factor.message,
    }


def _row(metric: str, value, threshold, passed: bool, message: str) -> dict:
    def dump(number) -> str | None:
        if number is None:
            return None
        if isinstance(number, Decimal):
            return format(number, "f")
        return str(number)

    return {
        "metric": metric,
        "value": dump(value),
        "threshold": dump(threshold),
        "passed": passed,
        "message": message,
    }


def _decimal(value, default: str) -> Decimal:
    return Decimal(str(value if value is not None else default))


def _min_dscr(product: Product) -> Decimal:
    return _decimal(product.params.get("min_dscr"), "1.25")
