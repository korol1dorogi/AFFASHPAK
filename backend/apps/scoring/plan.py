"""«Как получить одобрение» (XP2): the shortest set of scorecard steps after which the grade would
be C. Pure and deterministic: from the stored Score factors and their model version.

Stage 1 takes only the pass thresholds of failed factors («какие пороги нужно пройти»); when
passing all of them is not enough, stage 2 takes every higher step of the scales. Fewer steps
win; among equal plans — the smallest relative change of the metrics, then the §4 order of the
factors. Only what the client can change: the business age (by waiting), DSCR, debt/EBITDA,
revenue trend and concentration. A past overdue in the bureau cannot be undone, and the ФНС
flags are not in the Score. A factor without data gives no step: nothing to aim at yet.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal
from itertools import combinations, product

from apps.scoring import texts
from apps.scoring.policy import MetricRule, Scorecard, get_scorecard

TARGET_GRADE = "C"
PLAN_FACTORS = (
    "business_age_months",
    "dscr",
    "debt_to_ebitda",
    "revenue_trend",
    "counterparty_concentration",
)


@dataclass(frozen=True)
class PlanStep:
    metric: str
    current: Decimal
    target: Decimal
    points: int  # gained by the step
    message: str


@dataclass(frozen=True)
class ApprovalPlan:
    current_total: int
    target_total: int
    target_grade: str
    steps: tuple[PlanStep, ...]


@dataclass(frozen=True)
class _Option:
    order: int  # position of the factor in §4
    metric: str
    current: Decimal
    target: Decimal
    gain: int
    effort: Decimal  # relative change of the metric the step asks for


def approval_plan(factors: Sequence[Mapping], model_version: str) -> ApprovalPlan | None:
    """Plan for Score.factors (name, value, points); None — already C or better, or out of reach."""
    card = get_scorecard(model_version)
    current_total = sum(int(factor["points"]) for factor in factors)
    missing = _min_total(card, TARGET_GRADE) - current_total
    if missing <= 0:
        return None
    by_name = {factor["name"]: factor for factor in factors}
    thresholds: list[list[_Option]] = []  # stage 1: one option per failed factor
    every_step: list[list[_Option]] = []  # stage 2: all higher steps per factor
    for order, name in enumerate(PLAN_FACTORS):
        factor = by_name.get(name)
        if factor is None or factor["value"] is None:
            continue
        rule: MetricRule = getattr(card, name)
        value, points = Decimal(str(factor["value"])), int(factor["points"])
        options = [
            _Option(order, name, value, threshold, step_points - points, _effort(value, threshold))
            for threshold, step_points in rule.scale.steps
            if step_points > points
        ]
        if not options:
            continue
        every_step.append(options)
        passing = [option for option in options if option.target == rule.passed_threshold]
        if passing and not rule.passed(value):
            thresholds.append(passing)
    for groups in (thresholds, every_step):
        chosen = _fewest_steps(groups, missing)
        if chosen is not None:
            steps = sorted(chosen, key=lambda option: (-option.gain, option.order))
            target_total = current_total + sum(option.gain for option in steps)
            return ApprovalPlan(
                current_total=current_total,
                target_total=target_total,
                target_grade=card.grade(target_total),
                steps=tuple(_step(option) for option in steps),
            )
    return None


def _step(option: _Option) -> PlanStep:
    message = texts.plan_step(option.metric, option.current, option.target)
    return PlanStep(option.metric, option.current, option.target, option.gain, message)


def _min_total(card: Scorecard, grade: str) -> int:
    return next(total for total, name in card.grades if name == grade)


def _effort(current: Decimal, target: Decimal) -> Decimal:
    change = abs(target - current)
    return change / abs(current) if current else change


def _fewest_steps(groups: list[list[_Option]], missing: int) -> tuple[_Option, ...] | None:
    """At most one option per factor; the fewest steps adding `missing`, then the least effort."""
    for size in range(1, len(groups) + 1):
        plans = [
            plan
            for picked in combinations(groups, size)
            for plan in product(*picked)
            if sum(option.gain for option in plan) >= missing
        ]
        if plans:
            return min(
                plans,
                key=lambda plan: (
                    sum(option.effort for option in plan),
                    tuple(option.order for option in plan),
                    tuple(option.target for option in plan),
                ),
            )
    return None
