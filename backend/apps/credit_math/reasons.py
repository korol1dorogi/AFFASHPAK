"""Reason = one explained check: metric, value, threshold, passed, message (AGENTS.md)."""

from dataclasses import asdict, dataclass
from decimal import Decimal
from typing import Any

from apps.credit_math.money import Metric


@dataclass(frozen=True)
class Reason:
    metric: str
    value: Decimal | None
    threshold: Decimal | None
    passed: bool
    message: str

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def check_at_least(
    metric: str, result: Metric, threshold: Decimal, *, ok: str, fail: str
) -> Reason:
    """Passes when value ≥ threshold. An unavailable metric never passes; its note is shown."""
    if result.value is None:
        return Reason(metric, None, threshold, False, result.note or fail)
    passed = result.value >= threshold
    return Reason(metric, result.value, threshold, passed, ok if passed else fail)


def check_at_most(metric: str, result: Metric, threshold: Decimal, *, ok: str, fail: str) -> Reason:
    """Passes when value ≤ threshold. An unavailable metric never passes; its note is shown."""
    if result.value is None:
        return Reason(metric, None, threshold, False, result.note or fail)
    passed = result.value <= threshold
    return Reason(metric, result.value, threshold, passed, ok if passed else fail)
