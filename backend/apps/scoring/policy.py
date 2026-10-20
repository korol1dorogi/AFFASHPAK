"""Versioned thresholds of the scorecard and of the decision policy (decision-model.md §4, §6).

Thresholds are data, not constants spread over the code. Any change to a scale, a points value or
a grade boundary is a new `model_version`; a change to stop factors or decision rules is a new
`policy_version`. Old versions stay here: a stored Score must stay explainable.
"""

from dataclasses import dataclass
from decimal import Decimal
from types import MappingProxyType

D = Decimal


@dataclass(frozen=True)
class Scale:
    """Points by value: the first step the value reaches wins, otherwise `floor`.

    higher_is_better: value ≥ threshold, i.e. intervals [a; b). Otherwise value ≤ threshold,
    i.e. intervals (a; b]. `floor = None` — below the last step is a stop factor, not points.
    """

    steps: tuple[tuple[Decimal, int], ...]
    higher_is_better: bool
    floor: int | None

    @property
    def max_points(self) -> int:
        return self.steps[0][1]

    def points(self, value: Decimal) -> int:
        for threshold, points in self.steps:
            if value >= threshold if self.higher_is_better else value <= threshold:
                return points
        if self.floor is None:
            raise ValueError(f"{value} is outside the scale: it is a stop factor")
        return self.floor


@dataclass(frozen=True)
class MetricRule:
    scale: Scale
    passed_threshold: Decimal  # same direction as the scale
    unknown_points: int  # neutral points when the metric is None

    def passed(self, value: Decimal) -> bool:
        if self.scale.higher_is_better:
            return value >= self.passed_threshold
        return value <= self.passed_threshold


@dataclass(frozen=True)
class DscrRule(MetricRule):
    no_debt_points: int  # debt_service = 0 and cfads > 0


@dataclass(frozen=True)
class BkiRule:
    clean_points: int  # no current, no past overdue
    past_short_points: int  # past ≤ past_short_max_days
    past_long_points: int
    current_points: int  # current 1…current_max_days; more is stop factor С4
    past_short_max_days: int
    current_max_days: int
    unknown_points: int  # Check.status = unavailable

    @property
    def max_points(self) -> int:
        return self.clean_points


@dataclass(frozen=True)
class TransparentBusinessRule:
    clean_points: int
    one_flag_points: int  # mass_address or mass_director
    severe_points: int  # tax_arrears > 0 or both flags
    unknown_points: int

    @property
    def max_points(self) -> int:
        return self.clean_points


@dataclass(frozen=True)
class Scorecard:
    model_version: str
    business_age_months: MetricRule
    dscr: DscrRule
    debt_to_ebitda: MetricRule
    revenue_trend: MetricRule
    counterparty_concentration: MetricRule
    bki_history: BkiRule
    transparent_business: TransparentBusinessRule
    grades: tuple[tuple[int, str], ...]  # (min total, grade), best first
    lowest_grade: str
    key_metrics: tuple[str, ...]  # their None counts as «missing key metric»

    def grade(self, total: int) -> str:
        return next(
            (grade for minimum, grade in self.grades if total >= minimum), self.lowest_grade
        )


@dataclass(frozen=True)
class DecisionPolicy:
    policy_version: str
    stop_current_overdue_days: int
    stop_min_business_age_months: int
    max_missing_key_metrics: int
    purpose_min_length: int
    alternatives: MappingProxyType  # Product.kind → alternative Product.kind (rule П6)


SCORECARD_2026_10_V1 = Scorecard(
    model_version="scorecard-2026.10-v1",
    business_age_months=MetricRule(
        Scale(((D(36), 10), (D(24), 7), (D(12), 4), (D(6), 1)), higher_is_better=True, floor=None),
        passed_threshold=D(12),
        unknown_points=4,
    ),
    dscr=DscrRule(
        Scale(
            ((D("2.0"), 25), (D("1.5"), 18), (D("1.25"), 10), (D("1.0"), 4)),
            higher_is_better=True,
            floor=0,
        ),
        passed_threshold=D("1.25"),  # v1: min_dscr of the product, 1.25 everywhere
        unknown_points=12,
        no_debt_points=25,
    ),
    debt_to_ebitda=MetricRule(
        Scale(((D("2.0"), 15), (D("3.5"), 10), (D("5.0"), 4)), higher_is_better=False, floor=0),
        passed_threshold=D("3.5"),
        unknown_points=7,
    ),
    revenue_trend=MetricRule(
        Scale(((D("1.0"), 15), (D("0.9"), 10), (D("0.8"), 4)), higher_is_better=True, floor=0),
        passed_threshold=D("0.9"),
        unknown_points=7,
    ),
    counterparty_concentration=MetricRule(
        Scale(((D("0.3"), 10), (D("0.5"), 7), (D("0.7"), 3)), higher_is_better=False, floor=0),
        passed_threshold=D("0.5"),
        unknown_points=5,
    ),
    bki_history=BkiRule(
        clean_points=20,
        past_short_points=8,
        past_long_points=3,
        current_points=0,
        past_short_max_days=30,
        current_max_days=30,
        unknown_points=10,
    ),
    transparent_business=TransparentBusinessRule(
        clean_points=5, one_flag_points=2, severe_points=0, unknown_points=2
    ),
    grades=((90, "A"), (75, "B"), (60, "C"), (50, "D")),
    lowest_grade="E",
    key_metrics=("dscr", "revenue_trend", "counterparty_concentration"),
)

POLICY_2026_10_V1 = DecisionPolicy(
    policy_version="2026.10-v1",
    stop_current_overdue_days=30,
    stop_min_business_age_months=6,
    max_missing_key_metrics=1,
    purpose_min_length=10,
    alternatives=MappingProxyType(
        {
            "investment_loan": "leasing",
            "leasing": "investment_loan",  # only with collateral described
            "working_capital_loan": "overdraft",  # business 6–11 months old
        }
    ),
)

SCORECARDS = MappingProxyType({SCORECARD_2026_10_V1.model_version: SCORECARD_2026_10_V1})
POLICIES = MappingProxyType({POLICY_2026_10_V1.policy_version: POLICY_2026_10_V1})
CURRENT_MODEL_VERSION = SCORECARD_2026_10_V1.model_version
CURRENT_POLICY_VERSION = POLICY_2026_10_V1.policy_version


def get_scorecard(model_version: str = CURRENT_MODEL_VERSION) -> Scorecard:
    try:
        return SCORECARDS[model_version]
    except KeyError:
        raise KeyError(f"unknown model_version: {model_version}") from None


def get_policy(policy_version: str = CURRENT_POLICY_VERSION) -> DecisionPolicy:
    try:
        return POLICIES[policy_version]
    except KeyError:
        raise KeyError(f"unknown policy_version: {policy_version}") from None
