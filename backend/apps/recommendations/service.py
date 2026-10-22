"""Recommendation logic: pure domain code, no request and no DRF (the assistant S7 calls it too).

Order (docs/knowledge/credit.md, «Подбор»): stop factors → product conditions (requirements,
term and amount ranges) → size → ranking by fit to the task → reasons. Every sum comes from
credit_math; the rate is `rate_for(product, grade)` as in the future decision (D4 §5).

There are no checks before the application exists. The preliminary grade assumes a clean credit
history and no ФНС flags, and the `score_total` reason says so: the result is a preliminary
estimate, never the bank's decision. A product whose size cannot be computed (no turnover, no free
cash flow for DSCR) is left out: the contract has no `amount: null` yet (proposal to the lead).
"""

from collections.abc import Callable, Sequence
from dataclasses import dataclass, replace
from datetime import date
from decimal import Decimal

from apps.applications.models import Application, OfferStatus
from apps.applications.offers import monthly_payment, rate_for
from apps.business.models import Company, FinancialSnapshot, LegalForm
from apps.credit_math import (
    DEFAULT_MIN_DSCR,
    Metric,
    Reason,
    check_at_least,
    dscr,
    factoring_advance,
    factoring_commission,
    max_loan_by_dscr,
    overdraft_limit,
    round_money,
    working_capital_need_metric,
)
from apps.products.models import Product
from apps.recommendations.catalog import DEFAULT_TERM_MONTHS, NEED_PRODUCT_KINDS
from apps.scoring import (
    ScoreResult,
    ScoringInput,
    build_input,
    business_age_months,
    get_policy,
    get_scorecard,
    score,
    stop_factors,
)
from apps.scoring.inputs import SNAPSHOT_FIELDS
from apps.scoring.texts import number, percent, rubles

PRELIMINARY_CHECKS = {
    "bki": {"status": "ok", "data": {"current_overdue_days": 0, "past_overdue_max_days": 0}},
    "transparent_business": {
        "status": "ok",
        "data": {"mass_address": False, "mass_director": False, "tax_arrears": "0.00"},
    },
}
AUTO_OFFER_LOWEST_GRADE = "B"  # D4 §7: score_total passes for grades A–B


@dataclass(frozen=True)
class RecommendationInput:
    need_type: str
    amount: Decimal | None = None
    term_months: int | None = None
    invoice_amount: Decimal | None = None


@dataclass(frozen=True)
class Recommendation:
    product: Product
    amount: Decimal
    term_months: int
    rate: Decimal
    monthly_payment: Decimal | None
    reasons: tuple[Reason, ...]
    eligible: bool  # meets the product's conditions; an amount cut by a limit stays eligible
    rank: int = 0

    @property
    def fits(self) -> bool:
        return all(reason.passed for reason in self.reasons)


@dataclass(frozen=True)
class RecommendationResult:
    need_type: str
    offers: tuple[Recommendation, ...]
    stop_factors: tuple[Reason, ...]
    is_preliminary: bool = True


@dataclass(frozen=True)
class _Context:
    request: RecommendationInput
    inp: ScoringInput
    # The what-if (XP1) sizes with the offer's own rate: it needs neither a grade nor its reason.
    grade: str = ""
    grade_reason: Reason | None = None

    def metric(self, name: str) -> Decimal | None:
        return self.inp.metric(name)


@dataclass(frozen=True)
class _Size:
    limit: Decimal
    reasons: tuple[Reason, ...]


def latest_snapshot(company: Company) -> FinancialSnapshot | None:
    return company.snapshots.order_by("-period", "-id").first()


def scoring_input(
    company: Company, snapshot: FinancialSnapshot | None, on_date: date
) -> ScoringInput:
    values = None
    if snapshot is not None:
        values = {name: getattr(snapshot, name) for name in SNAPSHOT_FIELDS}
    record = {
        "legal_form": company.legal_form,
        "registry_status": company.registry_status,
        "registered_at": company.registered_at,
    }
    return build_input(record, values, PRELIMINARY_CHECKS, on_date)


def _param(product: Product, name: str) -> Decimal | None:
    value = (product.params or {}).get(name)
    return None if value is None else Decimal(str(value))


def _min_dscr(product: Product) -> Decimal:
    return _param(product, "min_dscr") or DEFAULT_MIN_DSCR


def _grade_reason(result: ScoreResult) -> Reason:
    card = get_scorecard(result.model_version)
    threshold = next(minimum for minimum, grade in card.grades if grade == AUTO_OFFER_LOWEST_GRADE)
    message = (
        f"Предварительная оценка риска: грейд {result.grade} ({result.total} из 100) — "
        "до проверки кредитной истории и данных ФНС"
    )
    return Reason(
        "score_total", Decimal(result.total), Decimal(threshold), result.total >= threshold, message
    )


def _requirements(product: Product, inp: ScoringInput) -> Reason:
    requirements = product.requirements or {}
    legal_forms = requirements.get("legal_forms", [LegalForm.IP, LegalForm.OOO])
    min_age = int(requirements.get("min_business_age_months", 0))
    age = business_age_months(inp.registered_at, inp.on_date)
    missing = []
    if inp.legal_form not in legal_forms:
        labels = ", ".join(LegalForm(form).label for form in legal_forms)
        missing.append(f"правовую форму: {labels}")
    if age < min_age:
        missing.append(f"возраст бизнеса от {min_age} мес, а бизнесу {age} мес")
    if missing:
        message = f"{product.name} требует {'; '.join(missing)}"
        return Reason("product_requirements", None, None, False, message)
    message = "Правовая форма и возраст бизнеса подходят"
    if product.collateral_required:
        message += "; нужен залог — обычно само покупаемое имущество"
    return Reason("product_requirements", None, None, True, message)


def _term(product: Product, requested: int | None) -> tuple[int, Reason | None]:
    """Requested or default term, clamped to the product's range; out of range is a reason."""
    wanted = requested or DEFAULT_TERM_MONTHS.get(product.kind, product.term_max_months)
    term = min(max(wanted, product.term_min_months), product.term_max_months)
    if requested is None or term == requested:
        return term, None
    message = f"Срок по продукту — от {product.term_min_months} до {product.term_max_months} мес"
    return term, Reason("term_months", Decimal(requested), None, False, message)


def _limit_reason(
    metric: str, limit: Decimal, requested: Decimal | None, *, ok: str, fail: str
) -> Reason:
    """A size limit against the client's amount; without an amount there is nothing to fail."""
    passed = requested is None or limit >= requested
    return Reason(metric, limit, requested, passed, ok if passed else fail)


def _dscr_limit(product: Product, ctx: _Context, rate: Decimal, term: int) -> Metric:
    cfads, service = ctx.metric("cfads"), ctx.metric("debt_service")
    if cfads is None or service is None:
        return Metric.unavailable("Нет данных о денежном потоке и платежах по долгам.")
    return max_loan_by_dscr(cfads, service, rate, term, _min_dscr(product))


def _dscr_reason(
    product: Product, limit: Decimal, ctx: _Context, rate: Decimal, term: int
) -> Reason:
    reserve = percent(_min_dscr(product) - 1)
    return _limit_reason(
        "max_loan_by_dscr", limit, ctx.request.amount,
        ok=f"Платёж посилен: допустимо до {rubles(limit)}",
        fail=(
            f"Чтобы платежи не съели запас {reserve}, сумма ограничена {rubles(limit)} "
            f"на {term} мес при {percent(rate)}"
        ),
    )  # fmt: skip


def _overdraft(product: Product, ctx: _Context, rate: Decimal, term: int) -> _Size | None:
    turnover, alpha = ctx.metric("cleaned_credit_turnover"), _param(product, "alpha")
    if turnover is None or alpha is None:
        return None
    limit = overdraft_limit(turnover, alpha)
    reason = _limit_reason(
        "overdraft_limit", limit, ctx.request.amount,
        ok=f"Лимит — {percent(alpha)} среднемесячных поступлений: {rubles(limit)}",
        fail=f"По оборотам доступно {rubles(limit)} — меньше запрошенного",
    )  # fmt: skip
    return _Size(limit, (reason,))


def _factoring(product: Product, ctx: _Context, rate: Decimal, term: int) -> _Size | None:
    invoice, beta = ctx.request.invoice_amount, _param(product, "beta")
    if invoice is None or beta is None:
        return None
    limit = factoring_advance(invoice, beta)
    advance = _limit_reason(
        "factoring_advance", limit, ctx.request.amount,
        ok=f"Сразу — {percent(beta)} суммы отгрузки: {rubles(limit)}",
        fail=f"Под эту отгрузку доступно {rubles(limit)}",
    )  # fmt: skip
    reasons = [advance]
    commission = _param(product, "commission")
    if commission is not None:
        fee = factoring_commission(invoice, commission)
        message = f"Разовая комиссия — {rubles(fee)} ({percent(commission)} отгрузки)"
        reasons.append(Reason("factoring_commission", fee, None, True, message))
    return _Size(limit, tuple(reasons))


def _working_capital_loan(
    product: Product, ctx: _Context, rate: Decimal, term: int
) -> _Size | None:
    by_dscr = _dscr_limit(product, ctx, rate, term)
    if by_dscr.value is None:
        return None
    need = working_capital_need_metric(
        ctx.metric("receivables"), ctx.metric("inventory"), ctx.metric("payables")
    )
    requested = ctx.request.amount
    if need.value is None:
        need_reason = Reason("working_capital_need", None, requested, False, need.note)
        limit = by_dscr.value
    else:
        need_reason = _limit_reason(
            "working_capital_need", need.value, requested,
            ok=(
                f"В дебиторке и запасах за вычетом кредиторки заморожено {rubles(need.value)} — "
                "больше бизнесу не нужно"
            ),
            fail=f"Потребность в оборотных средствах — {rubles(need.value)}, меньше запрошенного",
        )  # fmt: skip
        limit = min(need.value, by_dscr.value)
    dscr_reason = _dscr_reason(product, by_dscr.value, ctx, rate, term)
    return _Size(limit, (need_reason, dscr_reason))


def _long_loan(product: Product, ctx: _Context, rate: Decimal, term: int) -> _Size | None:
    """Investment loan and leasing: the payment must fit the DSCR reserve (products.md)."""
    by_dscr = _dscr_limit(product, ctx, rate, term)
    if by_dscr.value is None:
        return None
    return _Size(by_dscr.value, (_dscr_reason(product, by_dscr.value, ctx, rate, term),))


SIZERS: dict[str, Callable[[Product, _Context, Decimal, int], _Size | None]] = {
    "overdraft": _overdraft,
    "factoring": _factoring,
    "working_capital_loan": _working_capital_loan,
    "investment_loan": _long_loan,
    "leasing": _long_loan,
}


def _dscr_after(product: Product, ctx: _Context, payment: Decimal) -> Reason:
    min_dscr = _min_dscr(product)
    result = dscr(ctx.metric("cfads"), ctx.metric("debt_service") + payment)
    text = f"С новым платежом {rubles(payment)}/мес запас покрытия — "
    value = "" if result.value is None else number(result.value)
    return check_at_least(
        "dscr_after", result, min_dscr,
        ok=text + value,
        fail=f"{text}{value}, меньше нормы {number(min_dscr)}",
    )  # fmt: skip


def _evaluate(product: Product, ctx: _Context) -> Recommendation | None:
    sizer = SIZERS.get(product.kind)
    rate = rate_for(product, ctx.grade)
    term, term_reason = _term(product, ctx.request.term_months)
    size = None if sizer is None else sizer(product, ctx, rate, term)
    if size is None or size.limit <= 0:
        return None
    requirements = _requirements(product, ctx.inp)
    reasons = [ctx.grade_reason, requirements]
    if term_reason is not None:
        reasons.append(term_reason)
    reasons.extend(size.reasons)

    requested = ctx.request.amount
    allowed = size.limit
    if allowed > product.amount_max:
        allowed = product.amount_max
        passed = requested is None or requested <= product.amount_max
        message = f"Максимальная сумма по продукту — {rubles(product.amount_max)}"
        reasons.append(Reason("amount_max", product.amount_max, requested, passed, message))
    amount = round_money(allowed if requested is None else min(requested, allowed))
    amount_ok = amount >= product.amount_min
    if not amount_ok:
        message = f"Минимальная сумма по продукту — {rubles(product.amount_min)}"
        reasons.append(Reason("amount_min", amount, product.amount_min, False, message))

    payment = monthly_payment(product, amount, rate, term)
    if payment is not None:
        reasons.append(_dscr_after(product, ctx, payment))
    return Recommendation(
        product=product,
        amount=amount,
        term_months=term,
        rate=rate,
        monthly_payment=payment,
        reasons=tuple(reasons),
        eligible=requirements.passed and term_reason is None and amount_ok,
    )


def _products(kinds: Sequence[str]) -> list[Product]:
    products = Product.objects.filter(is_active=True, kind__in=kinds)
    return sorted(products, key=lambda product: (kinds.index(product.kind), product.code))


def _evaluated(products: list[Product], ctx: _Context) -> list[Recommendation]:
    found = (_evaluate(product, ctx) for product in products)
    return [recommendation for recommendation in found if recommendation is not None]


def recommend(
    company: Company, request: RecommendationInput, *, on_date: date
) -> RecommendationResult:
    """Ranked preliminary offers for the company's latest snapshot, or its stop factors."""
    inp = scoring_input(company, latest_snapshot(company), on_date)
    stops = stop_factors(inp)
    if stops:
        return RecommendationResult(request.need_type, (), tuple(stop.reason for stop in stops))
    result = score(inp)
    ctx = _Context(request, inp, result.grade, _grade_reason(result))

    kinds = NEED_PRODUCT_KINDS[request.need_type]
    offers = _evaluated(_products(kinds), ctx)
    if not any(offer.eligible for offer in offers):
        # Rule П6 alternatives of the policy, e.g. working capital loan → overdraft for a young
        # business; shown after the products of the need.
        alternatives = get_policy().alternatives
        extra = [alternatives[k] for k in kinds if alternatives.get(k) not in (None, *kinds)]
        offers += _evaluated(_products(extra), ctx)
    ranked = sorted(offers, key=lambda offer: not offer.eligible)  # stable: need order kept
    return RecommendationResult(
        need_type=request.need_type,
        offers=tuple(replace(offer, rank=index) for index, offer in enumerate(ranked, start=1)),
        stop_factors=(),
    )


# ── «Что если» под оффером (XP1) ──


class WhatIfUnavailable(Exception):
    """Nothing to play with: no active offer, or a revolving product without a fixed payment."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class TermOutOfRange(ValueError):
    """The term is outside the range of the offer's product."""


@dataclass(frozen=True)
class WhatIf:
    amount: Decimal
    term_months: int
    rate: Decimal
    monthly_payment: Decimal
    max_amount: Decimal | None  # None — the limit cannot be counted; the reason says why
    dscr_after: Decimal | None
    min_dscr: Decimal
    fits: bool
    reasons: tuple[Reason, ...]


def what_if(application: Application, amount: Decimal, term: int, *, on_date: date) -> WhatIf:
    """Payment, DSCR and the allowed amount for other terms of the active offer.

    The same sizers as the match (SIZERS) and the offer's own rate, so the numbers agree with the
    offer the pipeline made; a calculation, never a decision. An amount outside the product's
    limits is not an error but `fits = False` with the reason; a term outside them is.
    """
    offer = application.offers.filter(status=OfferStatus.ACTIVE).select_related("product").first()
    if offer is None:
        raise WhatIfUnavailable(
            "no_active_offer", "Посчитать другие условия можно, пока предложение банка действует."
        )
    product = offer.product
    sizer = SIZERS.get(product.kind)
    if product.is_revolving or sizer is None:
        raise WhatIfUnavailable(
            "revolving_product",
            "У этого продукта платёж зависит от использования — расчёт по сроку не нужен.",
        )
    if not product.term_min_months <= term <= product.term_max_months:
        raise TermOutOfRange(
            f"Срок по продукту — от {product.term_min_months} до {product.term_max_months} мес"
        )

    amount, rate, min_dscr = round_money(amount), offer.rate, _min_dscr(product)
    payment = monthly_payment(product, amount, rate, term)
    company = application.company
    request = RecommendationInput(
        need_type=application.need_type,
        amount=amount,
        term_months=term,
        invoice_amount=application.invoice_amount,
    )
    ctx = _Context(request, scoring_input(company, latest_snapshot(company), on_date))
    by_dscr = _dscr_limit(product, ctx, rate, term)
    size = None if by_dscr.value is None else sizer(product, ctx, rate, term)
    if size is None:  # no cash flow data, or no room for a new payment: None and the reason
        reason = Reason("max_loan_by_dscr", None, amount, False, by_dscr.note)
        return WhatIf(amount, term, rate, payment, None, None, min_dscr, False, (reason,))

    reasons = list(size.reasons)
    limit = size.limit
    if limit > product.amount_max:
        limit = product.amount_max
        message = f"Максимальная сумма по продукту — {rubles(product.amount_max)}"
        passed = amount <= product.amount_max
        reasons.append(Reason("amount_max", product.amount_max, amount, passed, message))
    if amount < product.amount_min:
        message = f"Минимальная сумма по продукту — {rubles(product.amount_min)}"
        reasons.append(Reason("amount_min", amount, product.amount_min, False, message))
    after = _dscr_after(product, ctx, payment)
    reasons.append(after)
    return WhatIf(
        amount=amount,
        term_months=term,
        rate=rate,
        monthly_payment=payment,
        max_amount=round_money(limit),
        dscr_after=after.value,
        min_dscr=min_dscr,
        fits=all(reason.passed for reason in reasons),
        reasons=tuple(reasons),
    )
