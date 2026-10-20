"""The policy config of decision-model.md §6: versions, grade boundaries, scale maxima."""

from decimal import Decimal

import pytest

from apps.scoring import CURRENT_MODEL_VERSION, CURRENT_POLICY_VERSION, get_policy, get_scorecard


def test_current_versions():
    assert CURRENT_MODEL_VERSION == "scorecard-2026.10-v1"
    assert CURRENT_POLICY_VERSION == "2026.10-v1"


def test_unknown_version_is_an_error():
    with pytest.raises(KeyError):
        get_scorecard("scorecard-1999")
    with pytest.raises(KeyError):
        get_policy("1999")


@pytest.mark.parametrize(
    ("total", "grade"),
    [(100, "A"), (90, "A"), (89, "B"), (75, "B"), (74, "C"), (60, "C"), (59, "D"), (50, "D"),
     (49, "E"), (0, "E")],
)  # fmt: skip
def test_grade_boundaries_are_inclusive(total, grade):
    assert get_scorecard().grade(total) == grade


def test_maxima_sum_to_100():
    card = get_scorecard()
    maxima = [
        card.business_age_months.scale.max_points,
        card.dscr.no_debt_points,
        card.debt_to_ebitda.scale.max_points,
        card.revenue_trend.scale.max_points,
        card.counterparty_concentration.scale.max_points,
        card.bki_history.max_points,
        card.transparent_business.max_points,
    ]
    assert maxima == [10, 25, 15, 15, 10, 20, 5]
    assert card.dscr.scale.max_points == card.dscr.no_debt_points


def test_neutral_points_are_inside_the_scale():
    """None is «don't know»: neither the best nor the worst (§4)."""
    card = get_scorecard()
    for rule in (
        card.dscr,
        card.debt_to_ebitda,
        card.revenue_trend,
        card.counterparty_concentration,
    ):
        assert 0 < rule.unknown_points < rule.scale.max_points
    assert 0 < card.bki_history.unknown_points < card.bki_history.max_points


def test_decision_policy_v1():
    policy = get_policy()
    assert policy.stop_current_overdue_days == 30
    assert policy.stop_min_business_age_months == 6
    assert policy.max_missing_key_metrics == 1
    assert policy.purpose_min_length == 10
    assert dict(policy.alternatives) == {
        "investment_loan": "leasing",
        "leasing": "investment_loan",
        "working_capital_loan": "overdraft",
    }


def test_scales_hold_no_float():
    card = get_scorecard()
    for rule in (
        card.dscr,
        card.debt_to_ebitda,
        card.revenue_trend,
        card.counterparty_concentration,
    ):
        assert all(isinstance(threshold, Decimal) for threshold, _ in rule.scale.steps)
        assert isinstance(rule.passed_threshold, Decimal)
