"""Bank statement built to target numbers (docs/data-spec.md §4.4) and checked by credit_math.

Monthly totals: M — revenue inflow, O — operating debits, K — the largest payer. The snapshot is
never set by hand: it is recomputed from the transactions by credit_math.statement (step 11).
"""

from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal
from math import ceil

from apps.credit_math.money import round_money
from apps.credit_math.statement import StatementMetrics, statement_metrics
from apps.demo_data.amounts import (
    add_months,
    money,
    month_days,
    month_start,
    r1000,
    split_amount,
)
from apps.demo_data.ids import INSPECTION_COUNTERPARTY, Counter, make_inn10
from apps.demo_data.reference import (
    DEMO,
    MONTH_NAMES,
    WEEKDAY_WEIGHTS,
    OkvedGroup,
)
from apps.demo_data.rng import Rng

STATEMENT_MONTHS = 18
MAX_SEASONALITY_HALVINGS = 3
ONE = Decimal(1)


class CounterpartyRegistry:
    """Counterparties with INN (inspection 02): same name → same organisation, one INN."""

    def __init__(self) -> None:
        self._counter = Counter(1)
        self._inns: dict[str, str] = {}

    def inn(self, name: str) -> str:
        if name not in self._inns:
            self._inns[name] = make_inn10(self._counter.next(), INSPECTION_COUNTERPARTY)
        return self._inns[name]


@dataclass(frozen=True)
class Payer:
    name: str
    share: Decimal | None  # window share of revenue; None — takes the rest of the month


@dataclass(frozen=True)
class Obligation:
    kind: str  # loan | leasing
    monthly_payment: Decimal
    payment_day: int
    opened_at: date
    opened_inside_month: int | None = None  # index of the statement month with the `loan` credit
    advance_payments: int = 0  # size of that credit in monthly payments
    lender: str = ""


@dataclass
class StatementPlan:
    company_key: str
    legal_form: str
    inn: str
    group: OkvedGroup
    months: tuple[str, ...]  # full months of the statement, oldest first
    window_sum: Decimal  # S_W
    cfads: Decimal
    tau: Decimal | None  # None — history shorter than 6 months, no trend
    kappa: Decimal
    top_payer: str
    other_payers: list[Payer]  # shares of revenue; the last one may take the rest
    has_retail: bool  # retail (no INN) takes the rest of every month
    suppliers: list[str]
    landlord: str
    obligations: list[Obligation] = field(default_factory=list)
    revenue_override: list[Decimal] | None = None  # persona 5: M(t) given explicitly


@dataclass(frozen=True)
class MonthlyTotals:
    revenue: list[Decimal]  # M
    opex: list[Decimal]  # O
    top_payer: list[Decimal]  # K
    others: list[list[Decimal]]  # per other payer
    retail: list[Decimal]


def statement_window(h: int) -> tuple[list[int], list[int], list[int]]:
    """Indices of the window, current 3 months and the trend base (§4.2), for h months."""
    window = list(range(max(0, h - 12), h))
    if h < 6:
        return window, [], []
    current = list(range(h - 3, h))
    base = list(range(h - 15, h - 12)) if h >= 15 else list(range(h - 6, h - 3))
    return window, current, base


def _seasonality(group: OkvedGroup, halvings: int) -> list[Decimal]:
    values = [Decimal(v) for v in group.seasonality]
    mean = sum(values) / 12
    for _ in range(halvings):
        values = [mean + (v - mean) / 2 for v in values]
    return [v / mean for v in values]


def revenue_months(plan: StatementPlan) -> list[Decimal]:
    """Steps 1–4: shape by seasonality and trend; trend and window sum hit exactly."""
    if plan.revenue_override is not None:
        return list(plan.revenue_override)
    h = len(plan.months)
    window, current, base = statement_window(h)
    tau = plan.tau if plan.tau is not None else ONE
    for halvings in range(MAX_SEASONALITY_HALVINGS + 1):
        season = _seasonality(plan.group, halvings)
        raw = []
        for k, period in enumerate(plan.months):
            t = STATEMENT_MONTHS - (h - 1 - k)  # calendar index of §4.4: 1…18
            month = int(period[5:7]) - 1
            exponent = (Decimal(t) - Decimal("12.5")) / 12
            raw.append(plan.window_sum / len(window) * season[month] * tau**exponent)
        m: list[Decimal | None] = [None] * h
        fixed = [k for k in range(h) if k not in window or k in base]
        for k in fixed:  # step 2: months before the window and the trend base
            m[k] = r1000(raw[k])
        rest_target = plan.window_sum
        if current:  # step 3: current 3 months = tau × base
            c3 = tau * sum(m[k] for k in base)
            raw_sum = sum(raw[k] for k in current)
            for k in current[:-1]:
                m[k] = r1000(c3 * raw[k] / raw_sum)
            m[current[-1]] = c3 - sum(m[k] for k in current[:-1])
            rest_target -= c3 + sum(m[k] for k in base if k in window)
        rest = [k for k in window if m[k] is None]
        if rest:  # step 4: the rest of the window takes the remaining sum
            raw_sum = sum(raw[k] for k in rest)
            for k in rest[:-1]:
                m[k] = r1000(rest_target * raw[k] / raw_sum)
            m[rest[-1]] = rest_target - sum(m[k] for k in rest[:-1])
        if all(v > 0 for v in m):
            return m
    raise ValueError(f"{plan.company_key}: revenue months stay ≤ 0 after halving seasonality")


def opex_months(plan: StatementPlan, revenue: list[Decimal]) -> list[Decimal]:
    """Step 5: operating debits so that cfads over the window is exact."""
    window, _, _ = statement_window(len(revenue))
    window_revenue = sum(revenue[k] for k in window)
    share = ONE - len(window) * plan.cfads / window_revenue
    opex = [r1000(v * share) for v in revenue]
    others = sum(opex[k] for k in window[:-1])
    opex[window[-1]] = window_revenue - len(window) * plan.cfads - others
    if min(opex) <= 0:
        raise ValueError(f"{plan.company_key}: operating debits must be > 0")
    return opex


def payer_months(plan: StatementPlan, revenue: list[Decimal]) -> MonthlyTotals:
    """Steps 6–7: the largest payer exactly at kappa; others below it; retail takes the rest."""
    window, _, _ = statement_window(len(revenue))
    top = [r1000(plan.kappa * v) for v in revenue]
    top[window[-1]] = plan.kappa * sum(revenue[k] for k in window) - sum(
        top[k] for k in window[:-1]
    )
    others: list[list[Decimal]] = [[] for _ in plan.other_payers]
    retail: list[Decimal] = []
    for k, v in enumerate(revenue):
        left = v - top[k]
        for j, payer in enumerate(plan.other_payers):
            if payer.share is None:
                continue
            amount = r1000(payer.share * v)
            others[j].append(amount)
            left -= amount
        if plan.has_retail:
            retail.append(left)
        else:
            others[-1].append(left)
            retail.append(Decimal(0))
    top_window = sum(top[k] for k in window)
    for series in others:
        if min(series) <= 0 or sum(series[k] for k in window) >= top_window:
            raise ValueError(f"{plan.company_key}: other payers must be > 0 and below kappa")
    if plan.has_retail and min(retail) <= 0:
        raise ValueError(f"{plan.company_key}: retail must be > 0")
    if min(top) <= 0:
        raise ValueError(f"{plan.company_key}: the largest payer must be > 0")
    return MonthlyTotals(revenue, [], top, others, retail)


def min_other_payers(kappa: Decimal, rest_share: Decimal, has_retail: bool) -> int:
    """Smallest count of other payers that keeps each strictly below kappa.

    Without retail ⌈1/κ⌉ + 1 (the domain's rule); with retail ⌈rest/κ⌉ + 1 — the same idea, but
    retail already takes most of the money and a coffee shop needs no twenty payers.
    """
    if has_retail:
        return ceil(rest_share / kappa) + 1
    return ceil(ONE / kappa) + 1


@dataclass
class _Tx:
    day: date
    seq: int
    direction: str
    amount: Decimal
    counterparty: str
    counterparty_inn: str | None
    category: str
    purpose: str


@dataclass
class _Builder:
    rng: Rng
    registry: CounterpartyRegistry
    txs: list[_Tx] = field(default_factory=list)
    contract: int = 0

    def add(self, day, direction, amount, counterparty, inn, category, purpose) -> None:
        self.txs.append(
            _Tx(day, len(self.txs), direction, amount, counterparty, inn, category, purpose + DEMO)
        )

    def next_contract(self) -> int:
        self.contract += 1
        return self.contract

    def days(self, period: str, count: int) -> list[date]:
        start, last = month_start(period), month_days(period)
        return sorted(start.replace(day=self.rng.between(1, last)) for _ in range(count))


def _prev_month_name(period: str) -> str:
    return MONTH_NAMES[(int(period[5:7]) - 2) % 12]


def _month_name(period: str) -> str:
    return MONTH_NAMES[int(period[5:7]) - 1]


def _split(b: _Builder, total: Decimal, count: int) -> list[Decimal]:
    return split_amount(total, [b.rng.between(50, 150) for _ in range(count)])


def _revenue_transactions(b: _Builder, plan: StatementPlan, totals: MonthlyTotals) -> None:
    payers = [(plan.top_payer, totals.top_payer)] + [
        (p.name, totals.others[j]) for j, p in enumerate(plan.other_payers)
    ]
    contracts = {name: b.next_contract() for name, _ in payers}
    for k, period in enumerate(plan.months):
        if plan.has_retail:
            start, last = month_start(period), month_days(period)
            days = [start.replace(day=d) for d in range(1, last + 1)]
            weights = [
                WEEKDAY_WEIGHTS[(day - timedelta(days=1)).weekday()] * b.rng.between(90, 110)
                for day in days
            ]
            for day, amount in zip(days, split_amount(totals.retail[k], weights), strict=True):
                sales_day = day - timedelta(days=1)
                b.add(
                    day, "credit", amount, "Эквайринг" + DEMO, None, "revenue",
                    f"Зачисление по эквайрингу за {sales_day:%d.%m}",
                )  # fmt: skip
        for name, series in payers:
            count = b.rng.between(1, 4)
            for day, amount in zip(b.days(period, count), _split(b, series[k], count), strict=True):
                b.add(
                    day, "credit", amount, name, b.registry.inn(name), "revenue",
                    f"Оплата по договору № {contracts[name]}",
                )  # fmt: skip


def _opex_transactions(b: _Builder, plan: StatementPlan, opex: list[Decimal]) -> None:
    payroll_share, rent_share, tax_share = (Decimal(s) for s in plan.group.opex_shares)
    for k, period in enumerate(plan.months):
        start = month_start(period)
        payroll = round_money(opex[k] * payroll_share)
        rent = round_money(opex[k] * rent_share)
        tax = round_money(opex[k] * tax_share)
        supplier_total = opex[k] - payroll - rent - tax
        b.add(
            start.replace(day=5), "debit", payroll, "Сотрудники" + DEMO, None, "payroll",
            f"Заработная плата за {_prev_month_name(period)}",
        )  # fmt: skip
        b.add(
            start.replace(day=b.rng.between(1, 3)), "debit", rent, plan.landlord,
            b.registry.inn(plan.landlord), "rent", f"Арендная плата за {_month_name(period)}",
        )  # fmt: skip
        b.add(start.replace(day=25), "debit", tax, "ФНС" + DEMO, None, "tax", "Налоговый платёж")
        count = b.rng.between(2, 6)
        for day, amount in zip(
            b.days(period, count), _split(b, supplier_total, count), strict=True
        ):
            name = b.rng.choice(plan.suppliers)
            b.add(
                day, "debit", amount, name, b.registry.inn(name), "supplier",
                f"Оплата поставщику по счёту № {b.next_contract()}",
            )  # fmt: skip


def _debt_transactions(b: _Builder, plan: StatementPlan) -> None:
    for obligation in plan.obligations:
        contract = b.next_contract()
        lender, inn = obligation.lender, b.registry.inn(obligation.lender)
        leasing = obligation.kind == "leasing"
        purpose = (
            f"Лизинговый платёж по договору № {contract}"
            if leasing
            else f"Платёж по кредитному договору № {contract}"
        )
        for k, period in enumerate(plan.months):
            day = month_start(period).replace(day=obligation.payment_day)
            opened = obligation.opened_inside_month
            if opened is not None and k == opened:
                amount = obligation.monthly_payment * obligation.advance_payments
                b.add(
                    day,
                    "credit",
                    amount,
                    lender,
                    inn,
                    "loan",
                    f"Выдача кредита по договору № {contract}",
                )
            if opened is None or k > opened:
                b.add(
                    day, "debit", obligation.monthly_payment, lender, inn, "loan_payment", purpose
                )


def _noise_transactions(b: _Builder, plan: StatementPlan, revenue: list[Decimal]) -> None:
    """Step 10: own transfers and refunds — excluded from every metric."""
    for k, period in enumerate(plan.months):
        for direction in ("credit", "debit"):
            count = b.rng.between(0, 2)
            for day in b.days(period, count):
                share = Decimal(b.rng.between(5, 15)) / 100
                b.add(
                    day, direction, round_money(revenue[k] * share), "Собственный счёт" + DEMO,
                    None, "own_transfer", "Перевод между своими счетами",
                )  # fmt: skip
        if b.rng.chance("0.5"):
            share = b.rng.decimal_between("0.1", "1.0", "0.1") / 100
            name = b.rng.choice(plan.suppliers)
            (day,) = b.days(period, 1)
            b.add(
                day, "credit", round_money(revenue[k] * share), name, b.registry.inn(name),
                "refund", "Возврат от поставщика",
            )  # fmt: skip


def account_masked(legal_form: str, inn: str) -> str:
    """§3.2: balance account (40802 ИП / 40702 ООО) + 810 + eight dots + last 4 INN digits."""
    return ("40802" if legal_form == "ip" else "40702") + "810" + "•" * 8 + inn[-4:]


@dataclass(frozen=True)
class BuiltStatement:
    record: dict
    totals: MonthlyTotals
    metrics: StatementMetrics


def build_statement(
    rng: Rng, plan: StatementPlan, registry: CounterpartyRegistry, as_of: date
) -> BuiltStatement:
    revenue = revenue_months(plan)
    opex = opex_months(plan, revenue)
    totals = payer_months(plan, revenue)
    totals = MonthlyTotals(revenue, opex, totals.top_payer, totals.others, totals.retail)

    builder = _Builder(rng, registry)
    _revenue_transactions(builder, plan, totals)
    _opex_transactions(builder, plan, opex)
    _debt_transactions(builder, plan)
    _noise_transactions(builder, plan, revenue)
    builder.txs.sort(key=lambda tx: (tx.day, tx.seq))
    transactions = [
        {
            "date": tx.day.isoformat(),
            "direction": tx.direction,
            "amount": money(tx.amount),
            "counterparty": tx.counterparty,
            "counterparty_inn": tx.counterparty_inn,
            "category": tx.category,
            "purpose": tx.purpose,
        }
        for tx in builder.txs
    ]
    period_from = month_start(plan.months[0])
    period_to = add_months(period_from, len(plan.months)) - timedelta(days=1)
    metrics = statement_metrics(transactions, as_of, period_from=period_from)
    _check(plan, totals, metrics)
    record = {
        "company": plan.company_key,
        "account_masked": account_masked(plan.legal_form, plan.inn),
        "period_from": period_from.isoformat(),
        "period_to": period_to.isoformat(),
        "transactions": transactions,
    }
    return BuiltStatement(record, totals, metrics)


def _check(plan: StatementPlan, totals: MonthlyTotals, metrics: StatementMetrics) -> None:
    """Step 11: the recomputed snapshot must hit the targets; a miss is a generator bug."""
    size = len(metrics.window)
    expected_debt = round_money(sum((o.monthly_payment for o in plan.obligations), Decimal(0)))
    window_revenue = sum(totals.revenue[-size:])
    checks = {
        "cleaned_credit_turnover": (
            metrics.cleaned_credit_turnover.value,
            round_money(window_revenue / size),
        ),
        "cfads": (metrics.cfads.value, round_money(plan.cfads)),
        "debt_service": (metrics.debt_service.value, expected_debt),
        "counterparty_concentration": (metrics.counterparty_concentration.value, plan.kappa),
    }
    if plan.tau is not None:
        checks["revenue_trend"] = (metrics.revenue_trend.value, plan.tau)
    for name, (got, want) in checks.items():
        if got is None or got != want:
            raise ValueError(f"{plan.company_key}: {name} = {got}, target {want}")
