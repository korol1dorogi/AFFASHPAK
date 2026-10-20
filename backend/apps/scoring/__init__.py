"""Scorecard of decision-model.md §4 (D5): pure functions, no ORM, no database.

Pipeline (L4) usage:
    inp = build_input(company, snapshot, checks, on_date=submitted_at.date())
    if stops := stop_factors(inp): ...decline (П1)...
    result = score(inp, min_dscr=product.params["min_dscr"])
    Score(grade=result.grade, total=result.total, factors=result.factors_payload(),
          model_version=result.model_version)
"""

from apps.scoring.age import business_age_months
from apps.scoring.factors import Factor
from apps.scoring.inputs import CheckResult, ScoringInput, build_input
from apps.scoring.policy import (
    CURRENT_MODEL_VERSION,
    CURRENT_POLICY_VERSION,
    get_policy,
    get_scorecard,
)
from apps.scoring.scorecard import ScoreResult, improvements, score
from apps.scoring.stop_factors import StopFactor, stop_factors

__all__ = [
    "CURRENT_MODEL_VERSION",
    "CURRENT_POLICY_VERSION",
    "CheckResult",
    "Factor",
    "ScoreResult",
    "ScoringInput",
    "StopFactor",
    "build_input",
    "business_age_months",
    "get_policy",
    "get_scorecard",
    "improvements",
    "score",
    "stop_factors",
]
