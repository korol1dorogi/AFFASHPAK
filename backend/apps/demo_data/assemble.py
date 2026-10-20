"""From resolved inputs to all records of one company: registry, people, statement, simulators."""

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from apps.demo_data import people, records, simulators
from apps.demo_data.ids import company_ids
from apps.demo_data.reference import REMAINING_MONTHS, Okved, OkvedGroup
from apps.demo_data.rng import Rng
from apps.demo_data.statements import (
    CounterpartyRegistry,
    Obligation,
    Payer,
    StatementPlan,
    build_statement,
)


@dataclass(frozen=True)
class Person:
    key: str
    username: str
    fio: str
    role: str  # signatory | preparer
    position: str
    login_enabled: bool


@dataclass
class CompanyInputs:
    key: str
    persona: str | None
    number: int
    legal_form: str
    group: OkvedGroup
    okved: Okved
    registered_at: date | None
    id_year: int  # year in OGRN; = registered_at.year unless the date is unknown
    name: str
    address: str
    registry_status: str
    in_egrul: bool
    people: list[Person]  # the first one is the signatory (director)
    months: tuple[str, ...]
    window_sum: Decimal
    cfads: Decimal
    tau: Decimal | None
    kappa: Decimal
    top_payer: str
    other_payers: list[Payer]
    has_retail: bool
    suppliers: list[str]
    landlord: str
    obligations: list[Obligation]
    reporting: dict[str, Decimal | None]
    bki_overdue: tuple[int, int]
    transparent_business: dict
    revenue_override: list[Decimal] | None = None


@dataclass
class Bundle:
    company: dict
    users: list[dict]
    memberships: list[dict]
    statement: dict
    snapshot: dict
    egrul: dict | None
    transparent_business: dict
    bki: dict
    monthly: object  # statements.MonthlyTotals, for tests and controls


@dataclass
class Registries:
    counterparties: CounterpartyRegistry = field(default_factory=CounterpartyRegistry)
    founders: people.FounderRegistry = field(default_factory=people.FounderRegistry)


def assemble(
    inputs: CompanyInputs, rng: Rng, statement_rng: Rng, registries: Registries, as_of: date
) -> Bundle:
    inn, ogrn = company_ids(inputs.legal_form, inputs.number, inputs.id_year)
    director = inputs.people[0]
    company = records.company(
        key=inputs.key,
        persona=inputs.persona,
        group=inputs.group,
        okved=inputs.okved,
        legal_form=inputs.legal_form,
        name=inputs.name,
        inn=inn,
        ogrn=ogrn,
        registered_at=inputs.registered_at,
        address=inputs.address,
        registry_status=inputs.registry_status,
        director_name=people.demo(director.fio),
        as_of=as_of,
    )
    users = [
        people.user(p.key, p.username, "client", p.fio, login_enabled=p.login_enabled)
        for p in inputs.people
    ]
    memberships = [people.membership(p.key, inputs.key, p.role, p.position) for p in inputs.people]
    founders = people.founders(
        rng,
        legal_form=inputs.legal_form,
        company_inn=inn,
        director_fio=director.fio,
        registry=registries.founders,
    )

    plan = StatementPlan(
        company_key=inputs.key,
        legal_form=inputs.legal_form,
        inn=inn,
        group=inputs.group,
        months=inputs.months,
        window_sum=inputs.window_sum,
        cfads=inputs.cfads,
        tau=inputs.tau,
        kappa=inputs.kappa,
        top_payer=inputs.top_payer,
        other_payers=inputs.other_payers,
        has_retail=inputs.has_retail,
        suppliers=inputs.suppliers,
        landlord=inputs.landlord,
        obligations=inputs.obligations,
        revenue_override=inputs.revenue_override,
    )
    built = build_statement(statement_rng, plan, registries.counterparties, as_of)
    snapshot = records.snapshot(inputs.key, inputs.months[-1], built.metrics, inputs.reporting)

    balances = simulators.obligation_balances(
        rng, inputs.obligations, REMAINING_MONTHS, inputs.reporting.get("debt")
    )
    current, past = inputs.bki_overdue
    return Bundle(
        company=company,
        users=users,
        memberships=memberships,
        statement=built.record,
        snapshot=snapshot,
        egrul=simulators.egrul(company, founders) if inputs.in_egrul else None,
        transparent_business=inputs.transparent_business,
        bki=simulators.bki(current, past, inputs.obligations, balances),
        monthly=built.totals,
    )
