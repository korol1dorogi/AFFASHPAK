"""XP2: «как получить одобрение» — the shortest set of scorecard steps to grade C, deterministic."""

from decimal import Decimal

import pytest

from apps.scoring import CURRENT_MODEL_VERSION, score
from apps.scoring.plan import approval_plan
from apps.scoring.tests.d4 import table_input


def factors(**values):
    """Score.factors as stored: (value, points) by factor name; unlisted factors are at maximum."""
    full = {
        "business_age_months": ("48", 10),
        "dscr": ("2.5000", 25),
        "debt_to_ebitda": ("1.5000", 15),
        "revenue_trend": ("1.1000", 15),
        "counterparty_concentration": ("0.2000", 10),
        "bki_history": ("0", 20),
        "transparent_business": (None, 5),
    }
    full.update(values)
    return [{"name": name, "value": v, "points": p, "message": ""} for name, (v, p) in full.items()]


def persona_5_plan():
    result = score(table_input("dependent_supplier"))
    return approval_plan(result.factors_payload(), result.model_version)


def test_persona_5_two_concrete_steps_to_grade_c():
    plan = persona_5_plan()
    assert (plan.current_total, plan.target_total, plan.target_grade) == (47, 60, "C")
    assert [(s.metric, s.current, s.target, s.points) for s in plan.steps] == [
        ("counterparty_concentration", Decimal("0.8000"), Decimal("0.5"), 7),
        ("revenue_trend", Decimal("0.8000"), Decimal("0.9"), 6),
    ]
    assert [s.message for s in plan.steps] == [
        (
            "Найдите ещё покупателей, чтобы на крупнейшего приходилось "
            "не больше 50% поступлений (сейчас 80%)"
        ),
        "Верните выручку хотя бы к 90% от прошлого года (сейчас 80%)",
    ]


def test_the_plan_is_deterministic():
    payload = score(table_input("dependent_supplier")).factors_payload()
    first = approval_plan(payload, CURRENT_MODEL_VERSION)
    assert all(approval_plan(payload, CURRENT_MODEL_VERSION) == first for _ in range(100))
    # The order the factors come in does not matter.
    assert approval_plan(list(reversed(payload)), CURRENT_MODEL_VERSION) == first
    assert approval_plan(payload[3:] + payload[:3], CURRENT_MODEL_VERSION) == first


def test_grade_c_or_better_needs_no_plan():
    result = score(table_input("furniture_maker"))  # persona 4: grade C, 65
    assert result.grade == "C"
    assert approval_plan(result.factors_payload(), result.model_version) is None


def test_beyond_the_thresholds_when_passing_them_is_not_enough():
    # 0 + 0 + 0 + 0 + 10 + 3 + 0 = 13: passing the four thresholds gives +37, not the +47 needed.
    plan = approval_plan(
        factors(
            dscr=("0.9000", 0),
            debt_to_ebitda=("6.0000", 0),
            revenue_trend=("0.7000", 0),
            counterparty_concentration=("0.9000", 0),
            bki_history=("45", 3),
            transparent_business=(None, 0),
        ),
        CURRENT_MODEL_VERSION,
    )
    assert plan.target_total >= 60 and plan.target_grade in {"A", "B", "C"}
    assert len(plan.steps) == 3
    assert any(step.target not in {Decimal("1.25"), Decimal("3.5"), Decimal("0.9"), Decimal("0.5")}
               for step in plan.steps)  # fmt: skip


def test_the_business_age_is_a_step_of_waiting():
    # 1 + 0 + 7 + 15 + 10 + 20 + 5 = 58 (D), 2 points short: 12 months (+3) is the smaller ask
    # than a DSCR from 0.9 to 1.25 (+10).
    plan = approval_plan(
        factors(business_age_months=("10", 1), dscr=("0.9000", 0), debt_to_ebitda=(None, 7)),
        CURRENT_MODEL_VERSION,
    )
    assert plan is not None
    assert [s.metric for s in plan.steps] == ["business_age_months"]
    assert (
        plan.steps[0].message
        == "Подайте заявку снова, когда бизнесу исполнится 1 год (сейчас 10 месяцев)"
    )


def test_out_of_reach_gives_no_plan():
    # No data on the account: only the age can grow, and 36 months add 9 points to 32.
    plan = approval_plan(
        factors(
            business_age_months=("7", 1),
            dscr=(None, 12),
            debt_to_ebitda=(None, 7),
            revenue_trend=(None, 7),
            counterparty_concentration=(None, 5),
            bki_history=("10", 0),
            transparent_business=(None, 0),
        ),
        CURRENT_MODEL_VERSION,
    )
    assert plan is None


@pytest.mark.parametrize("name", ["bki_history", "transparent_business"])
def test_the_bureau_and_fns_flags_are_never_steps(name):
    plan = persona_5_plan()
    assert name not in {step.metric for step in plan.steps}
