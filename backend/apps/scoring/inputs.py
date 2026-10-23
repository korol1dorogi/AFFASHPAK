"""Scoring input: FinancialSnapshot values, Check status and data, company dates.

`build_input` takes plain dicts shaped like the generator JSON (docs/data-spec.md §2: money as
strings, dates as ISO strings), so the pipeline (L4) and the tests feed the scorecard the same way.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from apps.credit_math import round_money, round_ratio, to_decimal

SOURCES = ("egrul", "transparent_business", "bki", "bank_account")
CHECK_STATUSES = frozenset(
    {"ok", "warning", "failed", "unavailable", "not_found", "restricted", "consent_missing"}
)
# No usable data: the source did not answer, hid the data, or was not asked (no consent).
# «No data» is not «bad»: the factor gets neutral points and an officer looks (SRC2).
NO_DATA_STATUSES = frozenset({"unavailable", "restricted", "consent_missing"})
SNAPSHOT_FIELDS = (
    "cleaned_credit_turnover", "cfads", "debt_service", "revenue", "cogs", "ebitda", "debt",
    "cash", "receivables", "inventory", "payables", "counterparty_concentration", "revenue_trend",
)  # fmt: skip
RATIO_FIELDS = frozenset({"counterparty_concentration", "revenue_trend"})


@dataclass(frozen=True)
class CheckResult:
    status: str
    data: Mapping[str, Any]

    @property
    def is_unavailable(self) -> bool:
        """The source did not answer: outage, timeout or an open breaker (scenario 7)."""
        return self.status == "unavailable"

    @property
    def has_no_data(self) -> bool:
        return self.status in NO_DATA_STATUSES


@dataclass(frozen=True)
class ScoringInput:
    legal_form: str
    registry_status: str
    registered_at: date | None
    on_date: date  # Application.submitted_at as a date
    snapshot: Mapping[str, Decimal | None] | None  # None — no snapshot at all
    checks: Mapping[str, CheckResult | None]  # None — the source was not requested yet

    def metric(self, name: str) -> Decimal | None:
        return None if self.snapshot is None else self.snapshot[name]

    def check(self, source: str) -> CheckResult | None:
        return self.checks.get(source)


def _date(value: date | str | None, name: str) -> date | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        raise TypeError(f"{name}: pass a date, not a datetime")
    return value if isinstance(value, date) else date.fromisoformat(value)


def _field(name: str, value) -> Decimal | None:
    """The scale of the model: money Decimal(14,2), coefficients Decimal(8,4) (data-model.md)."""
    if value is None:
        return None
    number = to_decimal(value, name)
    return round_ratio(number) if name in RATIO_FIELDS else round_money(number)


def _snapshot(snapshot: Mapping | None) -> dict[str, Decimal | None] | None:
    if snapshot is None:
        return None
    return {name: _field(name, snapshot.get(name)) for name in SNAPSHOT_FIELDS}


def _check(source: str, check: Mapping | None) -> CheckResult | None:
    if check is None:
        return None
    status = check["status"]
    if status not in CHECK_STATUSES:
        raise ValueError(f"{source}: unknown check status {status!r}")
    return CheckResult(status=status, data=dict(check.get("data") or {}))


def build_input(
    company: Mapping,
    snapshot: Mapping | None,
    checks: Mapping[str, Mapping | None],
    on_date: date | str,
) -> ScoringInput:
    """company: legal_form, registry_status, registered_at; snapshot: FinancialSnapshot fields;
    checks: source → {"status", "data"} (a missing source = not requested)."""
    unknown = set(checks) - set(SOURCES)
    if unknown:
        raise ValueError(f"unknown check sources: {sorted(unknown)}")
    return ScoringInput(
        legal_form=company["legal_form"],
        registry_status=company["registry_status"],
        registered_at=_date(company.get("registered_at"), "registered_at"),
        on_date=_date(on_date, "on_date"),
        snapshot=_snapshot(snapshot),
        checks={source: _check(source, checks.get(source)) for source in SOURCES},
    )
