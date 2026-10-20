"""Edge cases of docs/data-spec.md §10: «persona + differences», read by D5/L4 tests, not seeded.

Differences go through the statement (§4.4) or simulator data, never by editing the snapshot —
except g4 (null metrics cannot come from a statement) and e_all_unavailable (no snapshot at all).
`expected` holds only what §10 states; `note` quotes the rest. e_score_90_60_50 is left out:
§10 gives the scores, not the inputs that produce them.
"""

from collections.abc import Callable
from dataclasses import dataclass, field, replace
from datetime import date
from decimal import Decimal

from apps.demo_data.amounts import add_months, r1
from apps.demo_data.assemble import CompanyInputs, Registries, assemble
from apps.demo_data.ids import EDGE_NUMBERS, Counter
from apps.demo_data.personas import (
    FIXED_SEED,
    PERSONAS_BY_CODE,
    persona_inputs,
    statement_months,
)
from apps.demo_data.rng import Rng
from apps.demo_data.simulators import unavailable
from apps.demo_data.statements import Payer

D = Decimal
SOURCES = ("egrul", "transparent_business", "bki", "bank_account")

# §9.3: persona applications (inputs only — applications themselves are stage 2).
BASE_APPLICATIONS = {
    "coffee_shop": ("cash_gap", "overdraft_basic", "900000.00", 12, None, None),
    "retail_supplier": ("receivable_delay", "factoring_basic", "4500000.00", 2, "5000000.00", None),
    "garden_store": ("working_capital", "working_capital_loan_basic", "5300000.00", 12, None, None),
    "furniture_maker": (
        "capex", "investment_loan_basic", "8000000.00", 36, None,
        "Фрезерный станок с ЧПУ по договору поставки (демо)",
    ),
    "dependent_supplier": (
        "working_capital", "working_capital_loan_basic", "3000000.00", 12, None, None,
    ),
    "liquidating_company": ("cash_gap", "overdraft_basic", "500000.00", 6, None, None),
}  # fmt: skip
APPLICATION_FIELDS = (
    "need_type", "product", "requested_amount", "term_months", "invoice_amount",
    "collateral_description",
)  # fmt: skip

Change = Callable[[CompanyInputs, date], None]


@dataclass(frozen=True)
class Edge:
    code: str
    base: str
    note: str
    outcome: str | None = None
    grade: str | None = None
    total: int | None = None
    change: Change | None = None
    application: dict = field(default_factory=dict)
    unavailable: tuple[str, ...] = ()
    null_snapshot_fields: tuple[str, ...] = ()
    no_snapshot: bool = False


def _debt_service(amount: str) -> Change:
    def change(inputs: CompanyInputs, as_of: date) -> None:
        inputs.obligations = [replace(inputs.obligations[0], monthly_payment=D(amount))]

    return change


def _bki(current: int, past: int) -> Change:
    def change(inputs: CompanyInputs, as_of: date) -> None:
        inputs.bki_overdue = (current, past)

    return change


def _reporting(name: str, value: str) -> Change:
    def change(inputs: CompanyInputs, as_of: date) -> None:
        inputs.reporting = {**inputs.reporting, name: D(value)}

    return change


def _tau(value: str) -> Change:
    def change(inputs: CompanyInputs, as_of: date) -> None:
        inputs.tau = D(value)

    return change


def _kappa(value: str) -> Change:
    """Other payers keep their proportions (25 : 20 : 15 for persona 4) and fill 1 − κ."""

    def change(inputs: CompanyInputs, as_of: date) -> None:
        kappa = D(value)
        spec = PERSONAS_BY_CODE["furniture_maker"]
        weights = [D(s) for s in spec.other_shares]
        rest = 1 - kappa
        payers = inputs.other_payers
        inputs.kappa = kappa
        inputs.other_payers = [
            Payer(p.name, None if p.share is None else rest * w / sum(weights))
            for p, w in zip(payers, weights, strict=True)
        ]

    return change


def _age(months: int, tau: str | None = None) -> Change:
    """registered_at = ref_date − N months exactly (ref_date = as_of: no application yet)."""

    def change(inputs: CompanyInputs, as_of: date) -> None:
        registered = add_months(as_of, -months)
        first = add_months(registered, 1)
        h = min(18, (as_of.year - first.year) * 12 + as_of.month - first.month)
        window = min(12, h)
        monthly = inputs.window_sum / len(_window_of(inputs))
        inputs.registered_at = registered
        inputs.id_year = registered.year
        inputs.months = statement_months(as_of, h)
        inputs.window_sum = r1(monthly * window)
        # Debts that predate the statement cannot predate the business either.
        inputs.obligations = [
            replace(o, opened_at=max(o.opened_at, registered)) for o in inputs.obligations
        ]
        if h < 6:
            inputs.tau = None
        elif tau is not None:
            inputs.tau = D(tau)

    return change


def _window_of(inputs: CompanyInputs) -> tuple[str, ...]:
    return inputs.months[-12:]


def _no_registration_date(inputs: CompanyInputs, as_of: date) -> None:
    inputs.registered_at = None


def _all(*changes: Change) -> Change:
    def change(inputs: CompanyInputs, as_of: date) -> None:
        for one in changes:
            one(inputs, as_of)

    return change


EDGES = (
    Edge("g1", "garden_store", "D4 Г1: DSCR 1.2500 → 10 баллов, passed; max_loan_by_dscr = None "
         "→ manual_review", outcome="manual_review", change=_debt_service("240000")),
    Edge("g2", "garden_store", "D4 Г2: offer, не контроффер", outcome="offer",
         application={"requested_amount": "2009314.00"}),
    Edge("g3", "garden_store", "D4 Г3: 75 → B, контроффер 24 %", outcome="counteroffer",
         grade="B", total=75, change=_bki(0, 10)),
    Edge("g4", "coffee_shop", "D4 Г4: 79 → B, П5 manual_review", outcome="manual_review",
         grade="B", total=79,
         null_snapshot_fields=("revenue_trend", "counterparty_concentration")),
    Edge("g5", "liquidating_company", "D4 Г5: declined, source_unavailable не ставится",
         outcome="declined", unavailable=("bki",)),
    Edge("g6", "dependent_supplier", "D4 Г6: 37 → E, П3 manual_review", outcome="manual_review",
         grade="E", total=37, unavailable=("bki",)),
    Edge("g7", "furniture_maker", "D4 Г7: alternative_product, leasing_basic, 11 443 551 ₽",
         outcome="alternative_product", grade="B", total=82,
         change=_all(_bki(0, 0), _tau("1.00")),
         application={"collateral_description": None, "requested_amount": "12000000.00"}),
    Edge("g8", "retail_supplier", "D4 Г8: С3, declined, grade = null", outcome="declined",
         change=_reporting("ebitda", "0")),
    Edge("g9", "dependent_supplier", "D4 Г9: тренд 0.80 → 4 балла, passed = false"),
    Edge("g10", "coffee_shop", "D4 Г10: 86 → B, П3 manual_review; засеять нельзя",
         outcome="manual_review", grade="B", total=86, change=_no_registration_date),
    Edge("e_no_debt", "coffee_shop", "dscr None → 25 баллов, reason passed = true"),
    Edge("e_ebitda_negative", "retail_supplier", "С3, declined", outcome="declined",
         change=_reporting("ebitda", "-500000")),
    Edge("e_de_35", "retail_supplier", "debt_to_ebitda 3.5000 → 10 баллов, passed; итог 88",
         total=88, change=_reporting("debt", "25100000")),
    Edge("e_conc_edges_030", "furniture_maker", "концентрация 0.30 → 10 баллов, passed",
         change=_kappa("0.30")),
    Edge("e_conc_edges_050", "furniture_maker", "концентрация 0.50 → 7 баллов, passed",
         change=_kappa("0.50")),
    Edge("e_conc_edges_070", "furniture_maker", "концентрация 0.70 → 3 балла, не passed",
         change=_kappa("0.70")),
    Edge("e_trend_090", "garden_store", "тренд 0.90 → 10 баллов, passed; итог 87", total=87,
         change=_tau("0.90")),
    Edge("e_age_edges_5", "coffee_shop", "5 мес — С5, declined", outcome="declined",
         change=_age(5)),
    Edge("e_age_edges_6", "coffee_shop", "6 мес → 1 балл, не стоп-фактор", change=_age(6)),
    Edge("e_age_edges_12", "coffee_shop", "12 мес → 4 балла", change=_age(12)),
    Edge("e_age_edges_24", "coffee_shop", "24 мес → 7 баллов", change=_age(24)),
    Edge("e_age_edges_36", "coffee_shop", "36 мес → 10 баллов", change=_age(36)),
    Edge("e_overdue_30_30", "coffee_shop", "текущая 30 → 0 баллов, warning, не стоп: 72 → C, "
         "П5 manual_review", outcome="manual_review", grade="C", total=72,
         change=_bki(30, 30)),
    Edge("e_overdue_30_31", "coffee_shop", "текущая 31 → С4 declined", outcome="declined",
         change=_bki(31, 31)),
    Edge("e_past_30_30", "coffee_shop", "прошлая 30 → 8 баллов, passed; 80 → B", grade="B",
         total=80, change=_bki(0, 30)),
    Edge("e_past_30_31", "coffee_shop", "прошлая 31 → 3 балла, не passed; 75 → B", grade="B",
         total=75, change=_bki(0, 31)),
    Edge("e_all_unavailable", "coffee_shop", "снимка нет: 53 → D; П3 manual_review, "
         "source_unavailable = true", outcome="manual_review", grade="D", total=53,
         unavailable=SOURCES, no_snapshot=True),
    Edge("e_short_history", "coffee_shop", "тренд — последние 3 к предыдущим 3, «сезонность "
         "не учтена»; возраст 1 балл", change=_age(10)),
    Edge("e_over_amount_max", "coffee_shop", "П7 → counteroffer 900 000 ₽",
         outcome="counteroffer", application={"requested_amount": "12000000.00"}),
    Edge("e_no_invoice", "retail_supplier", "П2 → info_requested, fields = [invoice_amount]",
         outcome="info_requested", application={"invoice_amount": None}),
    Edge("e_young_wcl", "garden_store", "83 → B; П6 → alternative_product, overdraft_basic",
         outcome="alternative_product", grade="B", total=83, change=_age(8, tau="1.00")),
)  # fmt: skip


def _application(base: str, overrides: dict) -> dict:
    values = dict(zip(APPLICATION_FIELDS, BASE_APPLICATIONS[base], strict=True))
    values.update(overrides)
    return values


def _bank_account(statement: dict, h: int) -> dict:
    return {
        "status": "ok",
        "data": {
            "period": statement["period_to"][:7],
            "months": h,
            "account_masked": statement["account_masked"],
        },
    }


def build_edge_cases(generator_version: str, as_of: date, registries: Registries) -> list[dict]:
    counters = {form: Counter(*EDGE_NUMBERS) for form in ("ip", "ooo")}
    result = []
    for edge in EDGES:
        spec = PERSONAS_BY_CODE[edge.base]
        inputs = persona_inputs(spec, generator_version, as_of)
        inputs.key = f"edge_{edge.code}"
        inputs.persona = None
        inputs.number = counters[spec.legal_form].next()
        if edge.change is not None:
            edge.change(inputs, as_of)
        bundle = assemble(
            inputs,
            Rng(FIXED_SEED, generator_version, "edge", edge.code),
            Rng(FIXED_SEED, generator_version, "edge_statement", edge.code),
            registries,
            as_of,
        )
        checks = {
            "egrul": bundle.egrul,
            "transparent_business": bundle.transparent_business,
            "bki": bundle.bki,
            "bank_account": _bank_account(bundle.statement, len(inputs.months)),
        }
        for source in edge.unavailable:
            checks[source] = unavailable()
        snapshot = None if edge.no_snapshot else dict(bundle.snapshot)
        for name in edge.null_snapshot_fields:
            snapshot[name] = None
        result.append(
            {
                "code": edge.code,
                "company": bundle.company,
                "statement": None if edge.no_snapshot else bundle.statement,
                "snapshot": snapshot,
                "checks": checks,
                "application": _application(edge.base, edge.application),
                "expected": {
                    "outcome": edge.outcome,
                    "grade": edge.grade,
                    "total": edge.total,
                    "note": edge.note,
                },
            }
        )
    return result
