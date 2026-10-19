"""Decimal helpers shared by all credit formulas. float is rejected on purpose."""

from dataclasses import dataclass
from decimal import ROUND_FLOOR, ROUND_HALF_UP, Context, Decimal, localcontext

MONEY_STEP = Decimal("0.01")
RATIO_STEP = Decimal("0.0001")
RUBLE_STEP = Decimal("1")
DAYS_IN_YEAR = 365

# Enough digits for (1 + r) ** -n over 30-year monthly terms without visible drift.
_PRECISION = 50

Number = Decimal | int | str


def to_decimal(value: Number, name: str = "value") -> Decimal:
    """Convert int/str/Decimal to Decimal. float and bool are programmer errors."""
    if isinstance(value, bool | float):
        raise TypeError(f"{name}: float/bool are not allowed for money math, use Decimal or str")
    if isinstance(value, Decimal):
        result = value
    elif isinstance(value, int | str):
        result = Decimal(value)
    else:
        raise TypeError(f"{name}: unsupported type {type(value).__name__}")
    if not result.is_finite():
        raise ValueError(f"{name}: must be a finite number")
    return result


def round_money(value: Decimal) -> Decimal:
    """Round to kopecks, ROUND_HALF_UP."""
    return value.quantize(MONEY_STEP, rounding=ROUND_HALF_UP)


def round_ratio(value: Decimal) -> Decimal:
    """Round a coefficient to 4 decimal places, ROUND_HALF_UP."""
    return value.quantize(RATIO_STEP, rounding=ROUND_HALF_UP)


def floor_rubles(value: Decimal) -> Decimal:
    """Round down to whole rubles, keep the money scale (2 009 314.00)."""
    return value.quantize(RUBLE_STEP, rounding=ROUND_FLOOR).quantize(MONEY_STEP)


def precise() -> Context:
    """Context manager with high precision for intermediate calculations."""
    return localcontext(prec=_PRECISION)


@dataclass(frozen=True)
class Metric:
    """A metric value, or None with a human-readable reason why it cannot be computed.

    `note` may also carry a caveat for a valid value (e.g. a fallback comparison basis).
    """

    value: Decimal | None
    note: str | None = None

    @property
    def is_available(self) -> bool:
        return self.value is not None

    @classmethod
    def unavailable(cls, note: str) -> "Metric":
        return cls(value=None, note=note)
