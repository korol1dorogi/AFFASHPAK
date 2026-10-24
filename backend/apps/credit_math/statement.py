"""Bank statement → FinancialSnapshot metrics (docs/data-spec.md §4.2–4.3, credit.md).

Added by S2 with the lead's approval: the same aggregation serves the demo data generator and
the bank account adapter, so it lives here and nowhere else.

A transaction is a mapping with `date` (date or ISO string), `direction` (`credit` | `debit`),
`amount` (> 0), `category` and `counterparty_inn` (None for retail, staff, tax office and
own accounts).
"""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from apps.credit_math.metrics import counterparty_concentration, revenue_trend
from apps.credit_math.money import Metric, precise, round_money, to_decimal

INFLOW_CATEGORIES = frozenset({"revenue"})
OPEX_CATEGORIES = frozenset({"payroll", "rent", "supplier", "tax"})
DEBT_SERVICE_CATEGORIES = frozenset({"loan_payment"})
# category → allowed directions; own transfers, loans and refunds never count (credit.md).
ALLOWED = {
    "revenue": {"credit"},
    "own_transfer": {"credit", "debit"},
    "loan": {"credit"},
    "refund": {"credit"},
    "payroll": {"debit"},
    "rent": {"debit"},
    "supplier": {"debit"},
    "tax": {"debit"},
    "loan_payment": {"debit"},
}

WINDOW_MONTHS = 12
TREND_MONTHS = 3
YEAR_OVER_YEAR_MIN_MONTHS = 15
TREND_MIN_MONTHS = 6


@dataclass(frozen=True)
class MonthTotals:
    inflow: Decimal
    opex: Decimal
    debt_service: Decimal
    inflow_by_payer: Mapping[str, Decimal]


@dataclass(frozen=True)
class StatementMetrics:
    months: tuple[str, ...]  # all full months of the statement, "YYYY-MM"
    window: tuple[str, ...]  # last min(12, h) months
    cleaned_credit_turnover: Metric
    cfads: Metric
    debt_service: Metric
    counterparty_concentration: Metric
    revenue_trend: Metric


def _period(day: date) -> str:
    return f"{day.year:04d}-{day.month:02d}"


def statement_months(first: date, as_of: date) -> tuple[str, ...]:
    """Full months from the month of `first` up to the month before `as_of`."""
    year, month = first.year, first.month
    months = []
    while (year, month) < (as_of.year, as_of.month):
        months.append(f"{year:04d}-{month:02d}")
        year, month = (year + 1, 1) if month == 12 else (year, month + 1)
    return tuple(months)


def _as_date(value: date | str) -> date:
    return value if isinstance(value, date) else date.fromisoformat(value)


def monthly_totals(
    transactions: Iterable[Mapping], months: Iterable[str]
) -> dict[str, MonthTotals]:
    """Inflow (revenue), opex (payroll + rent + supplier + tax) and debt service per month."""
    wanted = tuple(months)
    inflow = {m: Decimal(0) for m in wanted}
    opex = {m: Decimal(0) for m in wanted}
    debt = {m: Decimal(0) for m in wanted}
    payers: dict[str, dict[str, Decimal]] = {m: {} for m in wanted}
    for tx in transactions:
        category, direction = tx["category"], tx["direction"]
        if direction not in ALLOWED.get(category, ()):
            raise ValueError(f"unexpected transaction: {category} / {direction}")
        amount = to_decimal(tx["amount"], "amount")
        if amount <= 0:
            raise ValueError("transaction amount must be > 0")
        month = _period(_as_date(tx["date"]))
        if month not in inflow:
            raise ValueError(f"transaction outside the statement months: {month}")
        if category in INFLOW_CATEGORIES:
            inflow[month] += amount
            inn = tx.get("counterparty_inn")
            if inn is not None:
                payers[month][inn] = payers[month].get(inn, Decimal(0)) + amount
        elif category in OPEX_CATEGORIES:
            opex[month] += amount
        elif category in DEBT_SERVICE_CATEGORIES:
            debt[month] += amount
    return {m: MonthTotals(inflow[m], opex[m], debt[m], payers[m]) for m in wanted}


def _trend(totals: Mapping[str, MonthTotals], months: tuple[str, ...]) -> Metric:
    h = len(months)
    if h < TREND_MIN_MONTHS:
        return Metric.unavailable("Выписка короче 6 месяцев, поэтому выручку сравнить не с чем.")
    current = months[-TREND_MONTHS:]
    year_over_year = h >= YEAR_OVER_YEAR_MIN_MONTHS
    base = months[-15:-12] if year_over_year else months[-6:-3]
    with precise():
        current_avg = round_money(sum(totals[m].inflow for m in current) / TREND_MONTHS)
        base_avg = round_money(sum(totals[m].inflow for m in base) / TREND_MONTHS)
    return revenue_trend(current_avg, base_avg, year_over_year=year_over_year)


def statement_metrics(
    transactions: Iterable[Mapping], as_of: date, *, period_from: date | None = None
) -> StatementMetrics:
    """Snapshot metrics over the window of the last min(12, h) full months before `as_of`.

    `period_from` — first day of the statement; without it the month of the earliest transaction.
    """
    txs = list(transactions)
    if period_from is None:
        if not txs:
            note = "Выписки нет, поэтому показатели по счёту не посчитать."
            empty = Metric.unavailable(note)
            return StatementMetrics((), (), empty, empty, empty, empty, empty)
        period_from = min(_as_date(tx["date"]) for tx in txs)
    months = statement_months(period_from, as_of)
    if not months:
        raise ValueError("the statement must cover at least one full month before as_of")
    totals = monthly_totals(txs, months)
    window = months[-WINDOW_MONTHS:]
    size = len(window)

    total_inflow = sum((totals[m].inflow for m in window), Decimal(0))
    total_opex = sum((totals[m].opex for m in window), Decimal(0))
    total_debt = sum((totals[m].debt_service for m in window), Decimal(0))
    by_payer: dict[str, Decimal] = {}
    for m in window:
        for inn, amount in totals[m].inflow_by_payer.items():
            by_payer[inn] = by_payer.get(inn, Decimal(0)) + amount
    # Retail (no INN) is many buyers, not one payer: it counts in the total only.
    top_inflow = max(by_payer.values(), default=Decimal(0))

    with precise():
        turnover = round_money(total_inflow / size)
        cfads = round_money((total_inflow - total_opex) / size)
        debt_service = round_money(total_debt / size)
    return StatementMetrics(
        months=months,
        window=window,
        cleaned_credit_turnover=Metric(turnover),
        cfads=Metric(cfads),
        debt_service=Metric(debt_service),
        counterparty_concentration=counterparty_concentration(top_inflow, total_inflow),
        revenue_trend=_trend(totals, months),
    )
