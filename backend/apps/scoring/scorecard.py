"""Scorecard (decision-model.md §4): seven factors → total 0–100 → grade A–E.

Scores the borrower, not the application: no amount, no term. The decision rules (L4) apply the
grade to the product, amount and checks. Stop factors come first: a stopped application is not
scored at all.
"""

from dataclasses import dataclass
from decimal import Decimal

from apps.scoring.factors import (
    Factor,
    bki_history_factor,
    business_age_factor,
    counterparty_concentration_factor,
    debt_to_ebitda_factor,
    dscr_factor,
    revenue_trend_factor,
    transparent_business_factor,
)
from apps.scoring.inputs import ScoringInput
from apps.scoring.policy import CURRENT_MODEL_VERSION, CURRENT_POLICY_VERSION, get_scorecard
from apps.scoring.stop_factors import stop_factors


@dataclass(frozen=True)
class ScoreResult:
    """Fields of the Score model plus the number of missing key metrics (rule П5)."""

    grade: str
    total: int
    factors: tuple[Factor, ...]
    model_version: str
    missing_key_metrics: int

    def factors_payload(self) -> list[dict]:
        """Score.factors as stored and served: ScoreFactor of docs/openapi.yaml."""
        return [factor.payload() for factor in self.factors]

    def factor(self, name: str) -> Factor:
        return next(f for f in self.factors if f.name == name)


def score(
    inp: ScoringInput,
    *,
    min_dscr: Decimal | None = None,
    model_version: str = CURRENT_MODEL_VERSION,
    policy_version: str = CURRENT_POLICY_VERSION,
) -> ScoreResult:
    """min_dscr — the product's `params.min_dscr` (the dscr pass threshold); default 1.25."""
    stops = stop_factors(inp, policy_version)
    if stops:
        codes = ", ".join(stop.code for stop in stops)
        raise ValueError(f"stop factors {codes}: the application is declined without scoring")
    card = get_scorecard(model_version)
    factors = (
        business_age_factor(inp, card),
        dscr_factor(inp, card, min_dscr),
        debt_to_ebitda_factor(inp, card),
        revenue_trend_factor(inp, card),
        counterparty_concentration_factor(inp, card),
        bki_history_factor(inp, card),
        transparent_business_factor(inp, card),
    )
    total = sum(f.points for f in factors)
    return ScoreResult(
        grade=card.grade(total),
        total=total,
        factors=factors,
        model_version=card.model_version,
        missing_key_metrics=sum(f.missing_key for f in factors if f.name in card.key_metrics),
    )


def improvements(result: ScoreResult) -> list[str]:
    """«What to improve» for a grade E decline (§7): failed factors, most lost points first.

    Ties keep the §4 order. A factor without a value (no data, source unavailable) gives no
    advice: there is nothing to improve until the data is there.
    """
    failed = [f for f in result.factors if not f.passed and f.value is not None]
    ordered = sorted(failed, key=lambda f: -f.lost_points)  # sorted() is stable
    return [text for factor in ordered for text in factor.improvements]
