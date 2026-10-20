"""Population of docs/data-spec.md §6, consistent with statements and simulators (§4, §5)."""

import re
from collections import Counter
from datetime import date
from decimal import Decimal

import pytest

from apps.credit_math import debt_to_ebitda, dscr
from apps.credit_math.statement import statement_metrics
from apps.demo_data.companies import labels
from apps.demo_data.reference import GENERATOR_VERSION
from apps.demo_data.rng import Rng
from apps.demo_data.simulators import transparent_business

D = Decimal
AS_OF = date(2026, 10, 1)
STOPS = {
    "stop_liquidating": 4, "stop_liquidated": 1, "stop_not_in_egrul": 1, "stop_ebitda": 3,
    "stop_overdue": 2, "stop_young": 1,
}  # fmt: skip
SEGMENTS = {"R1": 53, "R2": 73, "R3": 43, "R4": 41, "R5": 18}


@pytest.fixture(scope="module")
def population(dataset):
    snapshots = {s["company"]: s for s in dataset["financial_snapshots"]}
    statements = {s["company"]: s for s in dataset["statements"]}
    sims = dataset["simulators"]
    rows = []
    for company in dataset["companies"]:
        if company["_persona"] is not None:
            continue
        key, inn = company["_key"], company["inn"]
        rows.append(
            {
                "company": company,
                "snapshot": snapshots[key],
                "statement": statements[key],
                "egrul": sims["egrul"].get(inn),
                "tb": sims["transparent_business"][inn],
                "bki": sims["bki"][inn],
                "latent": dataset["_latent"][key],
            }
        )
    return rows


def test_quotas_for_240_companies(dataset, population):
    """§6.1 table: n = 240 → stop quotas 4/1/1/3/2/1 and segments 53/73/43/41/18."""
    assert len(population) == 240
    counts = Counter(row["latent"]["segment"] for row in population)
    assert counts == Counter({**STOPS, **SEGMENTS})


def test_labels_are_shuffled_deterministically():
    first = labels(Rng(2026, GENERATOR_VERSION, "segments"), 240)
    assert first == labels(Rng(2026, GENERATOR_VERSION, "segments"), 240)
    assert first != sorted(first)


def test_keys_numbers_and_people(population):
    numbers = {"ip": [], "ooo": []}
    for i, row in enumerate(population, start=1):
        company = row["company"]
        assert company["_key"] == f"co_{i:04d}"
        inn = company["inn"]
        numbers[company["legal_form"]].append(int(inn[4:9] if len(inn) == 10 else inn[4:10]))
    for values in numbers.values():
        assert values == list(range(1000, 1000 + len(values)))


def test_population_users_cannot_log_in(dataset):
    population_users = [
        u for u in dataset["users"] if re.fullmatch(r"demo_c\d{4}_(dir|acc)", u["username"])
    ]
    assert population_users
    assert all(u["_login_enabled"] is False for u in population_users)
    directors = {u["username"] for u in population_users if u["username"].endswith("_dir")}
    assert len(directors) == 240


def test_snapshot_equals_statement_for_every_company(dataset):
    """§11.3: the snapshot is what the statement gives, for all companies."""
    snapshots = {s["company"]: s for s in dataset["financial_snapshots"]}
    for statement in dataset["statements"]:
        metrics = statement_metrics(
            statement["transactions"], AS_OF,
            period_from=date.fromisoformat(statement["period_from"]),
        )  # fmt: skip
        snapshot = snapshots[statement["company"]]
        for field in ("cleaned_credit_turnover", "cfads", "debt_service"):
            assert str(getattr(metrics, field).value) == snapshot[field], (
                statement["company"],
                field,
            )
        for field in ("counterparty_concentration", "revenue_trend"):
            value = getattr(metrics, field).value
            assert (None if value is None else str(value)) == snapshot[field]


def test_trend_only_with_six_months_of_history(population):
    for row in population:
        months = _months(row["statement"])
        assert (row["snapshot"]["revenue_trend"] is None) == (months < 6)


def _months(statement) -> int:
    start = date.fromisoformat(statement["period_from"])
    end = date.fromisoformat(statement["period_to"])
    return (end.year - start.year) * 12 + end.month - start.month + 1


def test_factor_values_stay_in_spec_ranges(population):
    for row in population:
        s = row["snapshot"]
        if row["latent"]["segment"] == "stop_young":
            continue
        assert D("0.05") <= D(s["counterparty_concentration"]) <= D("0.90")
        if s["revenue_trend"] is not None:
            assert D("0.60") <= D(s["revenue_trend"]) <= D("1.25")
        coverage = dscr(D(s["cfads"]), D(s["debt_service"])).value
        assert coverage is None or D("0.40") <= coverage <= D("4.00") + D("0.0001")
        if s["ebitda"] is not None and D(s["ebitda"]) > 0 and D(s["debt"]) > 0:
            ratio = debt_to_ebitda(D(s["debt"]), D(s["ebitda"]), D(s["cash"])).value
            assert D("0.50") <= ratio <= D("8.00")


def test_stop_features(population):
    for row in population:
        segment, company = row["latent"]["segment"], row["company"]
        if segment == "stop_liquidating":
            assert company["registry_status"] == "liquidating"
            assert row["egrul"]["status"] == "warning"
        elif segment == "stop_liquidated":
            assert company["registry_status"] == "liquidated"
        else:
            assert company["registry_status"] == "active"
        assert (row["egrul"] is None) == (segment == "stop_not_in_egrul")
        if segment == "stop_ebitda":
            assert company["legal_form"] == "ooo" and D(row["snapshot"]["ebitda"]) <= 0
        if segment == "stop_overdue":
            assert row["bki"]["data"]["current_overdue_days"] > 30
            assert row["bki"]["status"] == "failed"
        else:
            assert row["bki"]["data"]["current_overdue_days"] <= 30
        if segment == "stop_young":
            # §6.1 says h = 2–4, but its own registered_at rule gives h ∈ {N − 1, N} for N = 3–5.
            assert 2 <= _months(row["statement"]) <= 5
            assert row["snapshot"]["revenue_trend"] is None


def test_reporting_only_for_ooo(population):
    fields = ("revenue", "cogs", "ebitda", "debt", "cash", "receivables", "inventory", "payables")
    with_reporting = 0
    for row in population:
        s = row["snapshot"]
        values = [s[f] for f in fields]
        if row["company"]["legal_form"] == "ip" or _months(row["statement"]) < 12:
            assert values == [None] * len(fields)  # §6.2: revenue is annual, h < 12 → no report
        elif values[0] is not None:
            with_reporting += 1
            assert None not in values
            if D(s["debt_service"]) == 0:
                assert s["debt"] == "0.00"
            if D(s["ebitda"]) > 0:
                assert D(s["cfads"]) * 12 <= D(s["ebitda"])
    assert with_reporting > 0


def test_bki_obligations_match_the_statement(population):
    for row in population:
        data = row["bki"]["data"]
        payments = sum((D(o["monthly_payment"]) for o in data["obligations"]), D(0))
        assert payments == D(row["snapshot"]["debt_service"])
        if row["snapshot"]["debt"] is not None and data["obligations"]:
            assert sum(D(o["balance"]) for o in data["obligations"]) == D(row["snapshot"]["debt"])
        loans = [t for t in row["statement"]["transactions"] if t["category"] == "loan"]
        opened_inside = [
            o for o in data["obligations"] if o["opened_at"] >= row["statement"]["period_from"]
        ]
        assert len(loans) == len(opened_inside)
        assert all(o["kind"] == "loan" for o in opened_inside)
        for o in data["obligations"]:
            assert o["opened_at"] >= row["company"]["registered_at"]


def test_mass_values_are_shared(population):
    """§5.2: flags are backed by data — each mass address / director is used at least twice."""
    for flag, field in (("mass_address", "address"), ("mass_director", "director_name")):
        values = Counter(row["company"][field] for row in population if row["tb"]["data"][flag])
        assert values, flag
        assert len(values) <= 3 and min(values.values()) >= 2, (flag, values)
    for row in population:
        if row["tb"]["data"]["mass_director"]:
            assert row["company"]["legal_form"] == "ooo"
        flagged = any(row["tb"]["data"][f] for f in ("mass_address", "mass_director"))
        flagged = flagged or D(row["tb"]["data"]["tax_arrears"]) > 0
        assert row["tb"]["status"] == ("warning" if flagged else "ok")


def test_entrepreneur_tax_flags():
    """§5.2: an ИП has no mass_director; its «debt or both» is always the tax debt (0 points)."""
    for i in range(200):
        rng = Rng(2026, GENERATOR_VERSION, "tb_test", str(i))
        one = transparent_business(rng, "one_flag", can_have_mass_director=False)["data"]
        assert (one["mass_address"], one["mass_director"], one["tax_arrears"]) == (
            True, False, "0.00",
        )  # fmt: skip
        debt = transparent_business(rng, "debt_or_both", can_have_mass_director=False)["data"]
        assert not debt["mass_address"] and not debt["mass_director"]
        assert D(debt["tax_arrears"]) > 0


def test_latent_risk(population):
    for row in population:
        latent = row["latent"]
        assert D("0") < D(latent["pd"]) <= D("0.9")
        assert isinstance(latent["default_12m"], bool)


@pytest.mark.skip(reason="D5 apps/scoring ещё нет: грейды A–E считать нечем (§11.5–11.8, D9)")
def test_grade_distribution_in_corridor():
    """§11.5–11.8: A ~15 · B ~30 · C ~25 · D ~15 · E ~10 · stop 5 %; n = 5000, Gini ≥ 0.4."""
