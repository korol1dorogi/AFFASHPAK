"""Financial metrics. Each returns a Metric: value or None + reason, never a fake 0."""

from dataclasses import dataclass
from decimal import Decimal

from apps.credit_math.money import (
    DAYS_IN_YEAR,
    Metric,
    Number,
    precise,
    round_money,
    round_ratio,
    to_decimal,
)


def dscr(cfads: Number, debt_service: Number) -> Metric:
    """DSCR = CFADS / debt service (principal + interest of all debts, same period).

    debt_service = 0 → None ("no debt"). CFADS ≤ 0 gives a value ≤ 0, which never passes.
    """
    flow = to_decimal(cfads, "cfads")
    service = to_decimal(debt_service, "debt_service")
    if service < 0:
        raise ValueError("debt_service must be >= 0")
    if service == 0:
        return Metric.unavailable("Долга нет: платежей по кредитам нет, DSCR не определён.")
    with precise():
        return Metric(round_ratio(flow / service))


def debt_to_ebitda(debt: Number, ebitda: Number, cash: Number = 0) -> Metric:
    """(Debt − cash) / EBITDA for the last 12 months. EBITDA ≤ 0 → None (stop factor)."""
    d = to_decimal(debt, "debt")
    e = to_decimal(ebitda, "ebitda")
    c = to_decimal(cash, "cash")
    if d < 0 or c < 0:
        raise ValueError("debt and cash must be >= 0")
    if e <= 0:
        return Metric.unavailable(
            "EBITDA ≤ 0: долговая нагрузка не определена — это стоп-фактор, а не хороший знак."
        )
    with precise():
        return Metric(round_ratio((d - c) / e))


@dataclass(frozen=True)
class CashConversionCycle:
    dso: Metric
    dio: Metric
    dpo: Metric
    ccc: Metric


def ccc(
    revenue: Number,
    cogs: Number,
    receivables: Number,
    inventory: Number,
    payables: Number,
    days_in_year: int = DAYS_IN_YEAR,
) -> CashConversionCycle:
    """DSO = AR/revenue·365; DIO = inventory/COGS·365; DPO = AP/COGS·365; CCC = DIO + DSO − DPO.

    COGS = 0 (services) → DIO and DPO are None, CCC is None.
    """
    rev = to_decimal(revenue, "revenue")
    cost = to_decimal(cogs, "cogs")
    ar = to_decimal(receivables, "receivables")
    inv = to_decimal(inventory, "inventory")
    ap = to_decimal(payables, "payables")
    if min(rev, cost, ar, inv, ap) < 0:
        raise ValueError("revenue, cogs and balances must be >= 0")

    with precise():
        dso = (
            Metric(round_ratio(ar / rev * days_in_year))
            if rev > 0
            else Metric.unavailable("Выручки нет: оборачиваемость дебиторки не определена.")
        )
        if cost > 0:
            dio = Metric(round_ratio(inv / cost * days_in_year))
            dpo = Metric(round_ratio(ap / cost * days_in_year))
        else:
            note = "Себестоимости нет (услуги): DIO и DPO не определены."
            dio = Metric.unavailable(note)
            dpo = Metric.unavailable(note)

    if dso.value is None or dio.value is None or dpo.value is None:
        cycle = Metric.unavailable("Финансовый цикл не определён: не хватает DSO, DIO или DPO.")
    else:
        cycle = Metric(dio.value + dso.value - dpo.value)
    return CashConversionCycle(dso=dso, dio=dio, dpo=dpo, ccc=cycle)


def working_capital_need(receivables: Number, inventory: Number, payables: Number) -> Decimal:
    """Receivables + inventory − payables, in rubles. Upper bound for a working capital loan.

    Do NOT compute it as CCC·revenue/365: DIO and DPO are measured in days of COGS.
    A negative value means suppliers finance the cycle and there is no need.
    """
    ar = to_decimal(receivables, "receivables")
    inv = to_decimal(inventory, "inventory")
    ap = to_decimal(payables, "payables")
    return round_money(ar + inv - ap)


def working_capital_need_metric(
    receivables: Number | None, inventory: Number | None, payables: Number | None
) -> Metric:
    """working_capital_need() for snapshot balances that may be null (decision-model.md §5).

    Any balance missing → None with a reason: then only DSCR limits a working capital loan.
    """
    if receivables is None or inventory is None or payables is None:
        return Metric.unavailable(
            "Нет остатков дебиторки, запасов или кредиторки: потребность в оборотных средствах "
            "не посчитать, сумму ограничивает только DSCR."
        )
    return Metric(working_capital_need(receivables, inventory, payables))


def counterparty_concentration(top_inflow: Number, total_inflow: Number) -> Metric:
    """Share of the largest payer in inflows (0..1)."""
    top = to_decimal(top_inflow, "top_inflow")
    total = to_decimal(total_inflow, "total_inflow")
    if top < 0 or total < 0:
        raise ValueError("inflows must be >= 0")
    if total == 0:
        return Metric.unavailable("Поступлений нет: концентрацию посчитать нельзя.")
    if top > total:
        raise ValueError("top_inflow cannot exceed total_inflow")
    with precise():
        return Metric(round_ratio(top / total))


def revenue_trend(current_avg: Number, base_avg: Number, *, year_over_year: bool = True) -> Metric:
    """current / base. Prefer year over year (same 3 months last year) to ignore seasonality.

    With less than 15 months of history pass the previous 3 months and year_over_year=False:
    the result carries a note that seasonality is not excluded.
    """
    current = to_decimal(current_avg, "current_avg")
    base = to_decimal(base_avg, "base_avg")
    if current < 0 or base < 0:
        raise ValueError("revenue averages must be >= 0")
    if base == 0:
        return Metric.unavailable("Нет базы для сравнения: выручка в базовом периоде равна нулю.")
    note = (
        None
        if year_over_year
        else "Истории меньше 15 месяцев: сравнение с предыдущими 3 месяцами, сезонность не учтена."
    )
    with precise():
        return Metric(round_ratio(current / base), note=note)


def exposure_at_default(drawn: Number, limit: Number, ccf: Number) -> Decimal:
    """EAD = drawn + CCF × undrawn part of the limit."""
    used = to_decimal(drawn, "drawn")
    total = to_decimal(limit, "limit")
    factor = to_decimal(ccf, "ccf")
    if used < 0 or total < 0 or not 0 <= factor <= 1:
        raise ValueError("drawn, limit must be >= 0 and ccf in [0, 1]")
    undrawn = max(total - used, Decimal(0))
    return round_money(used + factor * undrawn)


def expected_loss(pd: Number, lgd: Number, ead: Number) -> Decimal:
    """EL = PD × LGD × EAD (back office only, and only if PD comes from case data)."""
    p = to_decimal(pd, "pd")
    loss = to_decimal(lgd, "lgd")
    exposure = to_decimal(ead, "ead")
    if not (0 <= p <= 1 and 0 <= loss <= 1) or exposure < 0:
        raise ValueError("pd and lgd must be in [0, 1], ead >= 0")
    return round_money(p * loss * exposure)
