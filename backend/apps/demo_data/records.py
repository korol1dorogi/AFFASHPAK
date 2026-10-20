"""JSON records shared by personas, edge cases and the population (docs/data-spec.md §2)."""

from datetime import UTC, date, datetime, time
from decimal import Decimal

from apps.credit_math.money import Metric
from apps.credit_math.statement import StatementMetrics
from apps.demo_data.amounts import money
from apps.demo_data.reference import REGION, Okved, OkvedGroup

REPORTING_FIELDS = (
    "revenue",
    "cogs",
    "ebitda",
    "debt",
    "cash",
    "receivables",
    "inventory",
    "payables",
)


def utc_midnight(day: date) -> str:
    return datetime.combine(day, time(), tzinfo=UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def company(
    *,
    key: str,
    persona: str | None,
    group: OkvedGroup,
    okved: Okved,
    legal_form: str,
    name: str,
    inn: str,
    ogrn: str,
    registered_at: date | None,
    address: str,
    registry_status: str,
    director_name: str,
    as_of: date,
) -> dict:
    return {
        "_key": key,
        "_persona": persona,
        "_okved_group": group.code,
        "legal_form": legal_form,
        "name": name,
        "inn": inn,
        "ogrn": ogrn,
        "okved": okved.code,
        "okved_name": okved.name,
        "registered_at": registered_at.isoformat() if registered_at else None,
        "region": REGION,
        "address": address,
        "registry_status": registry_status,
        "director_name": director_name,
        "is_demo": True,
        "created_at": utc_midnight(as_of),
    }


def _ratio(metric: Metric) -> str | None:
    return None if metric.value is None else str(metric.value)


def _money(metric: Metric) -> str | None:
    return None if metric.value is None else money(metric.value)


def snapshot(
    company_key: str, period: str, metrics: StatementMetrics, reporting: dict[str, Decimal | None]
) -> dict:
    """FinancialSnapshot: statement fields recomputed from the statement, reporting given (§4.3)."""
    unknown = set(reporting) - set(REPORTING_FIELDS)
    if unknown:
        raise ValueError(f"not reporting fields: {sorted(unknown)}")
    record = {
        "company": company_key,
        "period": period,
        "source": "simulator",
        "cleaned_credit_turnover": _money(metrics.cleaned_credit_turnover),
        "cfads": _money(metrics.cfads),
        "debt_service": _money(metrics.debt_service),
        "counterparty_concentration": _ratio(metrics.counterparty_concentration),
        "revenue_trend": _ratio(metrics.revenue_trend),
    }
    for name in REPORTING_FIELDS:
        value = reporting.get(name)
        record[name] = None if value is None else money(value)
    return record
