"""D9 calibration: grade distribution and Gini of the scorecard on the generated population.

Steps of decision-model.md, «Результаты калибровки (D9)» → «Как воспроизвести». Only
aggregates come out; nothing per company is printed or stored.
"""

from collections import Counter, defaultdict
from dataclasses import dataclass
from decimal import Decimal

from apps.demo_data.build import generate
from apps.scoring import build_input, score, stop_factors

GRADES = ("A", "B", "C", "D", "E")
TARGETS = {"A": 15, "B": 30, "C": 25, "D": 15, "E": 10, "stop": 5}  # % of the population
CORRIDOR = Decimal(5)  # percentage points around each target
MIN_GINI = Decimal("0.4")
NOT_IN_REGISTRY = {"status": "failed", "data": {}}  # С2


@dataclass(frozen=True)
class Calibration:
    companies: int
    shares: dict[str, Decimal]  # grade or "stop" → % of the population, 2 decimals
    gini_expected: Decimal  # by the latent pd
    gini_realized: Decimal  # by the latent default_12m

    def deviations(self) -> dict[str, Decimal]:
        return {key: self.shares[key] - target for key, target in TARGETS.items()}

    def in_corridor(self) -> bool:
        return all(abs(delta) <= CORRIDOR for delta in self.deviations().values())


def calibrate(seed: int, n_companies: int) -> Calibration:
    data = generate(seed=seed, n_companies=n_companies)
    as_of = data["meta"]["as_of"]
    simulators = data["simulators"]
    snapshots = {snapshot["company"]: snapshot for snapshot in data["financial_snapshots"]}
    latent = data["_latent"]

    outcomes: Counter[str] = Counter()
    scored: list[tuple[int, Decimal, bool]] = []  # (total, pd, default_12m)
    population = [company for company in data["companies"] if company["_key"] in latent]
    for company in population:
        inn = company["inn"]
        checks = {
            "egrul": simulators["egrul"].get(inn, NOT_IN_REGISTRY),
            "transparent_business": simulators["transparent_business"][inn],
            "bki": simulators["bki"][inn],
            "bank_account": {"status": "ok", "data": {}},
        }
        inp = build_input(company, snapshots[company["_key"]], checks, on_date=as_of)
        if stop_factors(inp):
            outcomes["stop"] += 1
            continue
        result = score(inp)
        outcomes[result.grade] += 1
        risk = latent[company["_key"]]
        scored.append((result.total, Decimal(risk["pd"]), risk["default_12m"]))

    total = len(population)
    shares = {
        key: (Decimal(100) * outcomes[key] / total).quantize(Decimal("0.01"))
        for key in (*GRADES, "stop")
    }
    expected = gini([(points, pd) for points, pd, _ in scored])
    realized = gini([(points, Decimal(int(default))) for points, _, default in scored])
    return Calibration(total, shares, expected, realized)


def gini(rows: list[tuple[int, Decimal]]) -> Decimal:
    """Gini = 2·AUC − 1 over pairs (a, b), a ≠ b, weighted pd_a × (1 − pd_b) (data-spec §6.4).

    The pair counts 1 when total_a < total_b (the riskier one scored lower), 0.5 on a tie.
    O(n log n): pairs are summed per score instead of one by one.
    """
    by_total: dict[int, list[Decimal]] = defaultdict(list)
    for points, risk in rows:
        by_total[points].append(risk)
    bad_below = Decimal(0)  # Σ pd of companies with a lower score
    numerator = Decimal(0)
    for points in sorted(by_total):
        risks = by_total[points]
        bad_here = sum(risks, Decimal(0))
        for risk in risks:
            good = 1 - risk
            numerator += good * (bad_below + (bad_here - risk) / 2)
        bad_below += bad_here
    all_risks = [risk for _, risk in rows]
    bad, good = sum(all_risks, Decimal(0)), sum((1 - r for r in all_risks), Decimal(0))
    denominator = bad * good - sum((r * (1 - r) for r in all_risks), Decimal(0))
    if denominator == 0:
        raise ValueError("Gini needs both risky and safe companies")
    return (2 * numerator / denominator - 1).quantize(Decimal("0.001"))
