"""XP7: the credit policy in force and «what if a grade boundary moves» on the synthetic population.

The population is the generated one of the demo (apps.demo_data.build: seed 2026, 240 companies)
— the same companies as the bank queue and the D9 calibration. Scores do not depend on grade
boundaries, so every company is scored once (cached per process) and a what-if only lays the
same totals out on other boundaries: instant, deterministic, nothing stored.
"""

from collections import Counter
from dataclasses import dataclass
from functools import cache

from apps.scoring.inputs import build_input
from apps.scoring.policy import Scorecard, get_policy, get_scorecard
from apps.scoring.scorecard import score
from apps.scoring.stop_factors import stop_factors

GRADES = ("A", "B", "C", "D", "E")
STOP = "stop"
# What a grade means for an application (decision-model.md §6): A, B — an automatic offer,
# C, D — the officer looks, E and stop factors — a decline.
ZONE = {"A": "auto", "B": "auto", "C": "manual", "D": "manual", "E": "decline", STOP: "decline"}
NOT_IN_REGISTRY = {"status": "failed", "data": {}}


@dataclass(frozen=True)
class Population:
    companies: int
    totals: tuple[int | None, ...]  # None — stopped before scoring


@cache
def population() -> Population:
    from apps.demo_data.build import DEFAULT_N_COMPANIES, DEFAULT_SEED, generate

    data = generate(seed=DEFAULT_SEED, n_companies=DEFAULT_N_COMPANIES)
    snapshots = {snapshot["company"]: snapshot for snapshot in data["financial_snapshots"]}
    simulators = data["simulators"]
    totals: list[int | None] = []
    for company in data["companies"]:
        if company["_key"] not in data["_latent"]:
            continue  # the personas: they have their own scenarios
        inn = company["inn"]
        checks = {
            "egrul": simulators["egrul"].get(inn, NOT_IN_REGISTRY),
            "transparent_business": simulators["transparent_business"][inn],
            "bki": simulators["bki"][inn],
            "bank_account": {"status": "ok", "data": {}},
        }
        as_of = data["meta"]["as_of"]
        inp = build_input(company, snapshots[company["_key"]], checks, on_date=as_of)
        totals.append(None if stop_factors(inp) else score(inp).total)
    return Population(companies=len(totals), totals=tuple(totals))


def grade_of(total: int | None, boundaries: tuple[tuple[int, str], ...], lowest: str) -> str:
    if total is None:
        return STOP
    return next((grade for minimum, grade in boundaries if total >= minimum), lowest)


def distribution(grades: list[str]) -> list[dict]:
    counts = Counter(grades)
    return [{"grade": grade, "count": counts[grade]} for grade in (*GRADES, STOP)]


def zones(grades: list[str]) -> dict:
    counts = Counter(ZONE[grade] for grade in grades)
    return {zone: counts[zone] for zone in ("auto", "manual", "decline")}


def what_if(minimums: dict[str, int], card: Scorecard | None = None) -> dict:
    """The population on the current boundaries and on `minimums` (grade → min total)."""
    card = card or get_scorecard()
    people = population()
    proposed = tuple(sorted(((minimums[g], g) for g in ("A", "B", "C", "D")), reverse=True))
    before = [grade_of(total, card.grades, card.lowest_grade) for total in people.totals]
    after = [grade_of(total, proposed, card.lowest_grade) for total in people.totals]
    moves = Counter((old, new) for old, new in zip(before, after, strict=True) if old != new)
    return {
        "companies": people.companies,
        "changed": sum(moves.values()),
        "before": distribution(before),
        "after": distribution(after),
        "zones_before": zones(before),
        "zones_after": zones(after),
        "transitions": [
            {"from_grade": old, "to_grade": new, "count": count}
            for (old, new), count in sorted(moves.items())
        ],
    }


def overview() -> dict:
    """The policy in force: versions, grade boundaries, factor scales, stop factors and how the
    population lays out on them now."""
    card, policy = get_scorecard(), get_policy()
    current = {grade: minimum for minimum, grade in card.grades}
    impact = what_if(current, card)
    return {
        "model_version": card.model_version,
        "policy_version": policy.policy_version,
        "grades": [{"grade": grade, "min_total": minimum} for minimum, grade in card.grades],
        "lowest_grade": card.lowest_grade,
        "factors": _factors(card),
        "stop_factors": {
            "current_overdue_days": policy.stop_current_overdue_days,
            "min_business_age_months": policy.stop_min_business_age_months,
            "max_missing_key_metrics": policy.max_missing_key_metrics,
        },
        "population": {
            "companies": impact["companies"],
            "distribution": impact["before"],
            "zones": impact["zones_before"],
        },
    }


def _factors(card: Scorecard) -> list[dict]:
    rows = []
    for name in (
        "business_age_months",
        "dscr",
        "debt_to_ebitda",
        "revenue_trend",
        "counterparty_concentration",
    ):
        rule = getattr(card, name)
        rows.append(
            {
                "name": name,
                "max_points": rule.scale.max_points,
                "higher_is_better": rule.scale.higher_is_better,
                "steps": [
                    {"threshold": str(threshold), "points": points}
                    for threshold, points in rule.scale.steps
                ],
                "floor_points": rule.scale.floor,
                "passed_threshold": str(rule.passed_threshold),
                "unknown_points": rule.unknown_points,
            }
        )
    bki, fns = card.bki_history, card.transparent_business
    rows.append(
        {
            "name": "bki_history",
            "max_points": bki.max_points,
            "higher_is_better": None,
            "steps": [],
            "floor_points": bki.current_points,
            "passed_threshold": None,
            "unknown_points": bki.unknown_points,
        }
    )
    rows.append(
        {
            "name": "transparent_business",
            "max_points": fns.max_points,
            "higher_is_better": None,
            "steps": [],
            "floor_points": fns.severe_points,
            "passed_threshold": None,
            "unknown_points": fns.unknown_points,
        }
    )
    return rows
