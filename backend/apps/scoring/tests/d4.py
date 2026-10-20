"""Inputs of decision-model.md §8 «Входы персон» as literals, shaped like the generator JSON."""

from apps.scoring import build_input
from apps.scoring.tests.conftest import ON_DATE, UNAVAILABLE, bki, checks, company

# D4 §8 «Входы персон»: snapshot fields as strings, like the generator JSON (unlisted → null).
SNAPSHOTS = {
    "coffee_shop": {"cleaned_credit_turnover": "3000000", "cfads": "450000",
                    "debt_service": "0", "revenue_trend": "1.05",
                    "counterparty_concentration": "0.10"},
    "retail_supplier": {"cfads": "550000", "debt_service": "250000", "debt": "18600000",
                        "ebitda": "7000000", "cash": "600000", "revenue_trend": "1.00",
                        "counterparty_concentration": "0.60"},
    "garden_store": {"revenue": "36500000", "cogs": "29200000",
                     "receivables": "4500000", "inventory": "2400000",
                     "payables": "1600000", "cfads": "300000", "debt_service": "50000",
                     "revenue_trend": "0.95", "counterparty_concentration": "0.05"},
    "furniture_maker": {"cfads": "1800000", "debt_service": "1000000",
                        "revenue_trend": "0.97", "counterparty_concentration": "0.40"},
    "dependent_supplier": {"cfads": "330000", "debt_service": "300000",
                           "debt": "16800000", "ebitda": "4000000", "cash": "0",
                           "revenue_trend": "0.80", "counterparty_concentration": "0.80"},
}  # fmt: skip
SNAPSHOTS["bki_outage"] = SNAPSHOTS["coffee_shop"]
COMPANIES = {
    "coffee_shop": company("ip", 36),
    "retail_supplier": company("ooo", 72),
    "garden_store": company("ip", 96),
    "furniture_maker": company("ooo", 144),
    "dependent_supplier": company("ooo", 48),
    "bki_outage": company("ip", 36),
}
CHECKS = {
    "furniture_maker": checks(bki=bki(0, 10)),
    "bki_outage": checks(bki=UNAVAILABLE),
}


def table_input(code: str):
    return build_input(COMPANIES[code], SNAPSHOTS[code], CHECKS.get(code, checks()), ON_DATE)
