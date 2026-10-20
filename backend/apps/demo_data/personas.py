"""Demo personas from docs/demo.md whose numbers are fixed in docs/knowledge/credit.md.

Only personas 1, 2, 3, 5 for now: 4, 6, 7 wait for decision-model.md (D4) and data-spec.md (D7).
`figures` holds the inputs of credit_math in its own argument names; units:
- cleaned_credit_turnover, cfads, debt_service — rubles per month;
- revenue, cogs — rubles for the last 12 months; receivables, inventory, payables — balances;
- top_inflow, total_inflow — rubles for the same period;
- current_avg, base_avg — average monthly revenue: last 3 months and the same 3 months a year ago.
Derived metrics are never stored here: callers compute them with apps.credit_math.
Product parameters (alpha, beta, rates) belong to the catalog (D3) and are not part of the data.
"""

from datetime import date
from decimal import Decimal

from apps.credit_math import round_money
from apps.demo_data.companies import make_company
from apps.demo_data.rng import Rng

# Long enough for 18 months of statements and a year-over-year revenue trend.
PERSONA_MIN_AGE_YEARS = 3
PERSONA_MAX_AGE_YEARS = 10


def _money(value: str) -> str:
    return str(round_money(Decimal(value)))


PERSONAS = (
    {
        "code": "coffee_shop",
        "scenario": 1,
        "title": "Кофейня, ИП (демо)",
        "legal_form": "ip",
        "okved": "56.10",
        "need_type": "cash_gap",
        "figures": {"cleaned_credit_turnover": _money("3000000")},
    },
    {
        "code": "retail_supplier",
        "scenario": 2,
        "title": "Поставщик в розничную сеть, ООО (демо)",
        "legal_form": "ooo",
        "okved": "46.90",
        "need_type": "receivable_delay",
        "figures": {"invoice_amount": _money("5000000")},
    },
    {
        "code": "garden_store",
        "scenario": 3,
        "title": "Сезонный садовый магазин, ИП (демо)",
        "legal_form": "ip",
        "okved": "47.76",
        "need_type": "working_capital",
        "figures": {
            "revenue": _money("36500000"),
            "cogs": _money("29200000"),
            "receivables": _money("4500000"),
            "inventory": _money("2400000"),
            "payables": _money("1600000"),
            "cfads": _money("300000"),
            "debt_service": _money("50000"),
            "requested_amount": _money("5300000"),
            "term_months": 12,
        },
    },
    {
        "code": "dependent_supplier",
        "scenario": 5,
        "title": "Зависимый поставщик, ООО (демо)",
        "legal_form": "ooo",
        "okved": "46.90",
        "need_type": "working_capital",
        "figures": {
            "top_inflow": _money("2400000"),
            "total_inflow": _money("3000000"),
            "current_avg": _money("2400000"),
            "base_avg": _money("3000000"),
        },
    },
)


def make_personas(rng: Rng, *, as_of: date, taken_inns: set[str]) -> tuple[list[dict], list[dict]]:
    """Persona records and their companies. Each persona has its own RNG stream by code."""
    personas, companies = [], []
    for spec in PERSONAS:
        stream = rng.child(f"persona:{spec['code']}")
        while True:
            company = make_company(
                stream,
                as_of=as_of,
                legal_form=spec["legal_form"],
                okved=spec["okved"],
                min_age_years=PERSONA_MIN_AGE_YEARS,
                max_age_years=PERSONA_MAX_AGE_YEARS,
            )
            if company["inn"] not in taken_inns:
                break
        taken_inns.add(company["inn"])
        companies.append(company)
        personas.append(
            {
                "code": spec["code"],
                "scenario": spec["scenario"],
                "title": spec["title"],
                "company_inn": company["inn"],
                "need_type": spec["need_type"],
                "figures": dict(spec["figures"]),
            }
        )
    return personas, companies
