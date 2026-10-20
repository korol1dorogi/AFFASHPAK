"""Personas 1–7 (docs/data-spec.md §9, decision-model.md §8): fixed, independent of the seed.

Their streams use the seed string "fixed", so `seed` changes the population only (§11.1).
"""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from apps.demo_data.amounts import add_months
from apps.demo_data.assemble import CompanyInputs, Person
from apps.demo_data.naming import address, counterparty_names
from apps.demo_data.reference import DEMO, GROUPS_BY_CODE, IP_POSITION
from apps.demo_data.rng import Rng
from apps.demo_data.simulators import opened_before, tb_answer
from apps.demo_data.statements import STATEMENT_MONTHS, Obligation, Payer

FIXED_SEED = "fixed"
PAYMENT_DAY = 15  # §9.2: persona obligations are paid on the 15th
BANK = "Банк" + DEMO
LEASING_COMPANY = "Лизинговая компания" + DEMO
D = Decimal


@dataclass(frozen=True)
class PersonaSpec:
    number: int
    code: str
    legal_form: str
    name: str
    group: str
    okved: str
    registered_at: date
    registry_status: str
    signatory: str
    window_sum: str
    cfads: str
    tau: str
    kappa: str
    top_payer: str
    other_shares: tuple[str, ...]  # the last share of a B2B persona takes the rest of the month
    has_retail: bool
    obligations: tuple[tuple[str, str], ...] = ()  # (kind, monthly payment)
    reporting: tuple[tuple[str, str], ...] = ()
    bki_overdue: tuple[int, int] = (0, 0)
    revenue_override: tuple[int, ...] | None = None
    address: str | None = None
    accountant: str | None = None


PERSONAS = (
    PersonaSpec(
        1, "coffee_shop", "ip", "ИП Лаврова Анна Сергеевна — кофейня «Зерно и пар»" + DEMO,
        "food_service", "56.10", date(2023, 10, 1), "active", "Лаврова Анна Сергеевна",
        "36000000", "450000", "1.05", "0.10", "ООО «Офис на Северной»" + DEMO, (), True,
        address="000001, Демо-регион, г. Условный, ул. Кофейная, д. 7" + DEMO,
    ),
    PersonaSpec(
        2, "retail_supplier", "ooo", "ООО «Северный поставщик»" + DEMO,
        "wholesale", "46.90", date(2020, 10, 1), "active", "Громов Илья Петрович",
        "96000000", "550000", "1.00", "0.60", "ООО «Сеть Домашний»" + DEMO, ("0.25", "0.15"), False,
        obligations=(("loan", "250000"),),
        reporting=(("ebitda", "7000000"), ("debt", "18600000"), ("cash", "600000")),
    ),
    PersonaSpec(
        3, "garden_store", "ip",
        "ИП Соколова Марина Викторовна — садовый центр «Зелёный двор»" + DEMO,
        "garden", "47.76", date(2018, 10, 1), "active", "Соколова Марина Викторовна",
        "36500000", "300000", "0.95", "0.05", "ООО «Ландшафт-Про»" + DEMO, ("0.03",), True,
        obligations=(("loan", "50000"),),
        reporting=(
            ("revenue", "36500000"), ("cogs", "29200000"), ("receivables", "4500000"),
            ("inventory", "2400000"), ("payables", "1600000"),
        ),
    ),
    PersonaSpec(
        4, "furniture_maker", "ooo", "ООО «Дубрава Мебель»" + DEMO,
        "manufacturing", "31.09", date(2014, 10, 1), "active", "Орлов Сергей Николаевич",
        "144000000", "1800000", "0.97", "0.40", "ООО «Интерьер Групп»" + DEMO,
        ("0.25", "0.20", "0.15"), False,
        obligations=(("loan", "600000"), ("leasing", "400000")),
        bki_overdue=(0, 10),
        accountant="Белова Ольга Игоревна",
    ),
    PersonaSpec(
        5, "dependent_supplier", "ooo", "ООО «Опора Снаб»" + DEMO,
        "wholesale", "46.90", date(2022, 10, 1), "active", "Карпов Денис Андреевич",
        "32400000", "330000", "0.80", "0.80", "ООО «ТоргМаркет»" + DEMO, ("0.12", "0.08"), False,
        obligations=(("loan", "200000"), ("loan", "100000")),
        reporting=(("ebitda", "4000000"), ("debt", "16800000"), ("cash", "0")),
        revenue_override=(3_000_000,) * 6 + (2_800_000,) * 9 + (2_400_000,) * 3,
    ),
    PersonaSpec(
        6, "liquidating_company", "ooo", "ООО «Вектор Сервис»" + DEMO,
        "services", "62.01", date(2021, 10, 1), "liquidating", "Зуев Павел Олегович",
        "14400000", "96000", "0.90", "0.20", "ООО «Кедр Консалт»" + DEMO,
        ("0.18", "0.16", "0.16", "0.15", "0.15"), False,
    ),
    PersonaSpec(
        7, "bki_outage", "ip", "ИП Миронов Артём Валерьевич — кофейня «Северный ветер»" + DEMO,
        "food_service", "56.10", date(2023, 10, 1), "active", "Миронов Артём Валерьевич",
        "36000000", "450000", "1.05", "0.10", "ООО «Офис на Северной»" + DEMO, (), True,
    ),
)  # fmt: skip
PERSONAS_BY_CODE = {spec.code: spec for spec in PERSONAS}


def persona_rng(generator_version: str, scope: str, code: str) -> Rng:
    return Rng(FIXED_SEED, generator_version, scope, code)


def statement_months(as_of: date, count: int = STATEMENT_MONTHS) -> tuple[str, ...]:
    first = add_months(date(as_of.year, as_of.month, 1), -count)
    return tuple(f"{add_months(first, k):%Y-%m}" for k in range(count))


def persona_people(spec: PersonaSpec) -> list[Person]:
    position = IP_POSITION if spec.legal_form == "ip" else "Генеральный директор"
    result = [
        Person(f"u_{spec.code}", f"demo_{spec.code}", spec.signatory, "signatory", position, True)
    ]
    if spec.accountant:
        result.append(
            Person(
                "u_demo_accountant",
                "demo_accountant",
                spec.accountant,
                "preparer",
                "Главный бухгалтер",
                True,
            )
        )
    return result


def persona_inputs(spec: PersonaSpec, generator_version: str, as_of: date) -> CompanyInputs:
    rng = persona_rng(generator_version, "persona", spec.code)
    group = GROUPS_BY_CODE[spec.group]
    okved = next(o for o in group.okveds if o.code == spec.okved)
    months = statement_months(as_of)
    period_from = date.fromisoformat(months[0] + "-01")
    taken = {spec.top_payer}
    count = len(spec.other_shares)
    others = [
        # Without retail the last payer takes the rest of every month (§9.2).
        Payer(name, None if (not spec.has_retail and j == count - 1) else D(share))
        for j, (name, share) in enumerate(
            zip(counterparty_names(rng, count, taken), spec.other_shares, strict=True)
        )
    ]
    suppliers = counterparty_names(rng, rng.between(2, 8), taken)
    (landlord,) = counterparty_names(rng, 1, taken)
    obligations = [
        Obligation(
            kind=kind,
            monthly_payment=D(payment),
            payment_day=PAYMENT_DAY,
            opened_at=opened_before(rng, period_from, spec.registered_at, (1, 36)),
            lender=LEASING_COMPANY if kind == "leasing" else BANK,
        )
        for kind, payment in spec.obligations
    ]
    revenue_override = (
        [D(v) for v in spec.revenue_override] if spec.revenue_override is not None else None
    )
    return CompanyInputs(
        key=f"co_{spec.code}",
        persona=spec.code,
        number=spec.number,
        legal_form=spec.legal_form,
        group=group,
        okved=okved,
        registered_at=spec.registered_at,
        id_year=spec.registered_at.year,
        name=spec.name,
        address=spec.address or address(rng),
        registry_status=spec.registry_status,
        in_egrul=True,
        people=persona_people(spec),
        months=months,
        window_sum=D(spec.window_sum),
        cfads=D(spec.cfads),
        tau=D(spec.tau),
        kappa=D(spec.kappa),
        top_payer=spec.top_payer,
        other_payers=others,
        has_retail=spec.has_retail,
        suppliers=suppliers,
        landlord=landlord,
        obligations=obligations,
        reporting={name: D(value) for name, value in spec.reporting},
        bki_overdue=spec.bki_overdue,
        transparent_business=tb_answer(False, False, D(0)),
        revenue_override=revenue_override,
    )
