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
from apps.scoring import ScoringInput, business_age_months, score
from apps.scoring.inputs import SOURCES
from apps.scoring.policy import CURRENT_POLICY_VERSION, get_policy
from apps.scoring.scorecard import ScoreResult


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
    unavailable = [
        source for source in SOURCES if (check := inp.check(source)) and check.is_unavailable
    ]
    reasons = [_factor_reason(factor) for factor in result.factors]
    reasons.append(_score_reason(result))
    source_unavailable = bool(unavailable)
    for source in unavailable:
        reasons.append(
            {
                "metric": f"source_{source}",
                "value": None,
                "threshold": None,
                "passed": False,
                "message": "Источник не отвечает. Это не отказ — заявку проверит сотрудник",
            }
        )

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

    if source_unavailable or inp.registered_at is None:
        return pack(DecisionOutcome.MANUAL_REVIEW)
    if result.grade == "E":
        texts: list[str] = []
        for factor in sorted(result.factors, key=lambda item: item.lost_points, reverse=True):
            texts.extend(factor.improvements)
        return pack(DecisionOutcome.DECLINED, improvements=texts)
    if _needs_officer(result, product):
        _cap, extra = _size(product, application, inp, result.grade, application.term_months)
        return pack(DecisionOutcome.MANUAL_REVIEW, extra=extra)

    chosen = product
    if not _fits(product, application, inp):
        alternative = _alternative(product, application, inp)
        if alternative is None:
            return pack(
                DecisionOutcome.DECLINED,
                improvements=["Под этот запрос нет другого подходящего продукта"],
            )
        chosen = alternative

    term = _clamp_term(chosen, application.term_months)
    rate = rate_for(chosen, result.grade)
    cap, extra = _size(chosen, application, inp, result.grade, term)
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
    if by_dscr is None:
        return None, []
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
        return None, []
    alpha = _decimal(product.params.get("alpha"), "0.3")
    limit = min(overdraft_limit(turnover, alpha), product.amount_max)
    passed = limit >= requested
    text = (
        f"Лимит — {alpha} среднемесячных поступлений: {limit} ₽"
        if passed
        else f"По оборотам доступно {limit} ₽ — меньше запрошенного"
    )
    return limit, [_row("overdraft_limit", limit, requested, passed, text)]


def _factoring_size(
    product: Product, application: Application, requested: Decimal
) -> tuple[Decimal | None, list[dict]]:
    invoice = application.invoice_amount
    if invoice is None:
        return None, []
    beta = _decimal(product.params.get("beta"), "0.9")
    limit = min(factoring_advance(invoice, beta), product.amount_max)
    passed = limit >= requested
    text = (
        f"Сразу — {beta} суммы отгрузки: {limit} ₽"
        if passed
        else f"Под эту отгрузку доступно {limit} ₽"
    )
    reasons = [_row("factoring_advance", limit, requested, passed, text)]
    commission = product.params.get("commission")
    if commission is not None:
        fee = factoring_commission(invoice, _decimal(commission, "0"))
        reasons.append(_row("factoring_commission", fee, None, True, f"Разовая комиссия — {fee} ₽"))
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
        f"Платёж посилен: допустимо до {limit} ₽"
        if passed
        else f"Сумма ограничена {limit} ₽ на {term} мес при ставке {rate}"
    )
    return _row("max_loan_by_dscr", limit, requested, passed, text)


def _need_reason(need, requested: Decimal) -> dict:
    if need.value is None:
        return _row("working_capital_need", None, requested, False, need.note or "")
    passed = need.value >= requested
    text = (
        f"В обороте заморожено {need.value} ₽ — больше бизнесу не нужно"
        if passed
        else f"Потребность в оборотных средствах — {need.value} ₽, меньше запрошенного"
    )
    return _row("working_capital_need", need.value, requested, passed, text)


def _dscr_after(
    product: Product, inp: ScoringInput, amount: Decimal, rate: Decimal, term: int
) -> dict:
    payment = annuity_payment(amount, rate, term)
    current = inp.metric("debt_service") or Decimal(0)
    cfads = inp.metric("cfads")
    if cfads is None:
        return _row("dscr_after", None, _min_dscr(product), False, "Нет денежного потока")
    metric = dscr(cfads, current + payment)
    threshold = _min_dscr(product)
    passed = metric.value is not None and metric.value >= threshold
    text = f"С новым платежом {payment} ₽/мес запас покрытия — {metric.value}"
    return _row("dscr_after", metric.value, threshold, passed, text)


def _amount_improvements(
    product: Product, inp: ScoringInput, offered: Decimal, requested: Decimal, rate: Decimal
) -> list[str]:
    if offered >= requested or product.kind in {"overdraft", "factoring"}:
        return []
    texts = ["Снизьте текущие платежи по долгам"]
    cfads, service = inp.metric("cfads"), inp.metric("debt_service")
    if cfads is None or service is None:
        return texts
    longer = max_loan_by_dscr(cfads, service, rate, product.term_max_months, _min_dscr(product))
    if longer.value is not None:
        texts.insert(0, f"При сроке {product.term_max_months} мес допустимо {longer.value} ₽")
    return texts


def _score_reason(result: ScoreResult) -> dict:
    return {
        "metric": "score_total",
        "value": str(result.total),
        "threshold": "75",
        "passed": result.grade in {"A", "B"},
        "message": f"Грейд {result.grade} ({result.total} из 100)",
    }


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
