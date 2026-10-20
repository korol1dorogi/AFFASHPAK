"""Inputs for the scoring tests: D4 §8 tables as literals, and the demo data generator.

Personas come from `generate(n_companies=0)`: personas and edge cases do not depend on the seed or
the population (data-spec §6.6), so the population is skipped.
"""

from datetime import date

import pytest

from apps.demo_data.build import generate
from apps.scoring import build_input

OK_BKI = {"status": "ok", "data": {"current_overdue_days": 0, "past_overdue_max_days": 0}}
OK_TB = {
    "status": "ok",
    "data": {"mass_address": False, "mass_director": False, "tax_arrears": "0.00"},
}
OK_EGRUL = {"status": "ok", "data": {"registry_status": "active"}}
OK_ACCOUNT = {"status": "ok", "data": {}}
UNAVAILABLE = {"status": "unavailable", "data": {}}
ON_DATE = date(2026, 10, 1)


def checks(**overrides) -> dict:
    """All four checks ok, as in D4 §8, with per-source overrides."""
    result = {
        "egrul": OK_EGRUL,
        "transparent_business": OK_TB,
        "bki": OK_BKI,
        "bank_account": OK_ACCOUNT,
    }
    result.update(overrides)
    return result


def bki(current: int, past: int) -> dict:
    status = "failed" if current > 30 else "warning" if current or past > 30 else "ok"
    return {
        "status": status,
        "data": {"current_overdue_days": current, "past_overdue_max_days": past},
    }


def company(legal_form: str, age_months: int | None, registry_status: str = "active") -> dict:
    if age_months is None:
        registered_at = None
    else:
        total = ON_DATE.year * 12 + ON_DATE.month - 1 - age_months
        registered_at = date(total // 12, total % 12 + 1, 1)
    return {
        "legal_form": legal_form,
        "registry_status": registry_status,
        "registered_at": registered_at,
    }


@pytest.fixture(scope="session")
def dataset() -> dict:
    return generate(n_companies=0)


def _dataset_checks(dataset: dict, inn: str, has_snapshot: bool) -> dict:
    sims = dataset["simulators"]
    egrul = sims["egrul"].get(inn) or {"status": "failed", "data": {}}  # §5.1: no record → С2
    return {
        "egrul": egrul,
        "transparent_business": sims["transparent_business"][inn],
        "bki": sims["bki"][inn],
        # The generator keeps no bank_account answer for companies: a statement means «ok» (§5.1).
        "bank_account": OK_ACCOUNT if has_snapshot else UNAVAILABLE,
    }


@pytest.fixture(scope="session")
def persona_input(dataset):
    """Scoring input of a persona as the pipeline would see it on `meta.as_of`."""
    companies = {c["_key"]: c for c in dataset["companies"]}
    snapshots = {s["company"]: s for s in dataset["financial_snapshots"]}
    on_date = date.fromisoformat(dataset["meta"]["as_of"])

    def build(code: str, **check_overrides):
        key = dataset["personas"][code]["company"]
        record = companies[key]
        found = _dataset_checks(dataset, record["inn"], has_snapshot=True)
        found.update(check_overrides)
        return build_input(record, snapshots[key], found, on_date)

    return build


@pytest.fixture(scope="session")
def edge_case(dataset):
    """(input, expected) of an `edge_cases[]` record of the generator (data-spec §10)."""
    edges = {e["code"]: e for e in dataset["edge_cases"]}
    on_date = date.fromisoformat(dataset["meta"]["as_of"])

    def build(code: str):
        edge = edges[code]
        inp = build_input(edge["company"], edge["snapshot"], edge["checks"], on_date)
        return inp, edge["expected"]

    return build
