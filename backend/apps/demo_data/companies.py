"""Company population: quotas, risk segments, features by score buckets (docs/data-spec.md §6).

Pass 1 draws every company from its own stream `company|{i}` (people from `people|{i}`), pass 2
spreads the shared «mass» addresses and directors (§5.2), pass 3 builds statements from
`statement|{i}`. The latent risk of §6.4 comes from `latent|{i}`.
"""

import math
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal

from apps.credit_math import debt_to_ebitda, dscr
from apps.demo_data import reference as ref
from apps.demo_data.amounts import (
    add_months,
    full_months_between,
    largest_remainder,
    month_start,
    r1,
    r1000,
)
from apps.demo_data.assemble import CompanyInputs, Person
from apps.demo_data.ids import POPULATION_FIRST_NUMBER, Counter
from apps.demo_data.naming import address, counterparty_names, ip_name, ooo_name
from apps.demo_data.people import random_fio
from apps.demo_data.rng import Rng
from apps.demo_data.simulators import bki_overdue, opened_before, transparent_business
from apps.demo_data.statements import (
    STATEMENT_MONTHS,
    Obligation,
    Payer,
    min_other_payers,
    statement_window,
)

D = Decimal
BANK = "Банк" + ref.DEMO
LEASING_COMPANY = "Лизинговая компания" + ref.DEMO
MAX_REDRAWS = 20


def labels(rng: Rng, n: int) -> list[str]:
    """§6.1: 5 % stop quotas by weight, the rest R1–R5, both by largest remainder, shuffled."""
    stop_total = int((n * D(ref.STOP_SHARE)).quantize(D(1), rounding=ROUND_HALF_UP))
    stop_counts = largest_remainder(stop_total, [D(w) for _, w in ref.STOP_QUOTAS])
    segment_counts = largest_remainder(n - stop_total, [D(w) for _, w in ref.SEGMENT_SHARES])
    result = []
    for (code, _), count in zip(ref.STOP_QUOTAS, stop_counts, strict=True):
        result += [code] * count
    for (code, _), count in zip(ref.SEGMENT_SHARES, segment_counts, strict=True):
        result += [code] * count
    return rng.shuffled(result)


def draw_bucket(rng: Rng, main: int, count: int, p_main: str) -> int:
    """Main bucket with p_main, the rest split equally between the neighbours (§6.3)."""
    if rng.chance(p_main):
        return main
    neighbours = [b for b in (main - 1, main + 1) if 0 <= b < count]
    return rng.choice(neighbours)


def _in_bucket(value: Decimal, bounds: tuple[str | None, str | None], *, upper_closed: bool):
    low, high = bounds
    if low is not None and (value <= D(low) if upper_closed else value < D(low)):
        return False
    if high is None:
        return True
    return value <= D(high) if upper_closed else value < D(high)


def _value(rng: Rng, bounds: tuple[str, str]) -> Decimal:
    return rng.decimal_between(*bounds)


@dataclass
class Draft:
    """Pass-1 result: everything but the statement and the shared «mass» values."""

    index: int
    label: str
    inputs: CompanyInputs
    flags: dict
    latent: dict


def _turnover(rng: Rng, legal_form: str) -> Decimal:
    """§6.2: lognormal, median by legal form, σ(ln T) = 0.6, clipped, r1000 (float only here)."""
    raw = ref.TURNOVER_MEDIAN[legal_form] * math.exp(ref.TURNOVER_SIGMA * rng.normal())
    low, high = ref.TURNOVER_BOUNDS
    return r1000(D(str(round(min(max(raw, low), high)))))


def _statement_months(registered_at: date, as_of: date) -> tuple[str, ...]:
    """§4.2: from the month after registration, at most 18 full months before as_of."""
    first = add_months(month_start(f"{registered_at:%Y-%m}"), 1)
    end = date(as_of.year, as_of.month, 1)
    h = min(STATEMENT_MONTHS, full_months_between(first, end))
    if h <= 0:
        raise ValueError("a company needs at least one full month of statement")
    start = add_months(end, -h)
    return tuple(f"{add_months(start, k):%Y-%m}" for k in range(h))


def _obligations(
    rng: Rng, debt_service: Decimal, months: tuple[str, ...], registered_at: date
) -> list[Obligation]:
    """§4.4 step 8: 1–3 debts summing to debt_service, paid every month of the window."""
    if debt_service == 0:
        return []
    count = rng.between(1, 3)
    payments = [r1(debt_service * D(s)) for s in ref.OBLIGATION_SHARES[: count - 1]]
    payments.append(debt_service - sum(payments))
    window, _, _ = statement_window(len(months))
    period_from = month_start(months[0])
    result = []
    for payment in payments:
        kind = "leasing" if rng.chance(ref.LEASING_SHARE) else "loan"
        inside = None
        latest_inside = min(ref.OPENED_INSIDE_MAX_MONTH, window[0]) - 1
        if kind == "loan" and latest_inside >= 0 and rng.chance(ref.OPENED_INSIDE_SHARE):
            inside = rng.between(0, latest_inside)
        day = rng.between(*ref.PAYMENT_DAY)
        if inside is None:
            opened = opened_before(rng, period_from, registered_at, ref.OPENED_BEFORE_MONTHS)
            advance = 0
        else:
            opened = month_start(months[inside]).replace(day=day)
            advance = rng.between(*ref.LOAN_PAYMENTS_IN_ADVANCE)
        result.append(
            Obligation(
                kind=kind,
                monthly_payment=payment,
                payment_day=day,
                opened_at=opened,
                opened_inside_month=inside,
                advance_payments=advance,
                lender=LEASING_COMPANY if kind == "leasing" else BANK,
            )
        )
    return result


def _people(rng: Rng, i: int, legal_form: str) -> list[Person]:
    tag = f"c{i:04d}"
    if legal_form == "ip":
        position = ref.IP_POSITION
    else:
        names, weights = zip(*ref.OOO_DIRECTOR_POSITIONS, strict=True)
        position = rng.weighted(names, weights)
    result = [
        Person(f"u_{tag}_dir", f"demo_{tag}_dir", random_fio(rng), "signatory", position, False)
    ]
    if rng.chance(ref.ACCOUNTANT_SHARE[legal_form]):
        names, weights = zip(*ref.ACCOUNTANT_POSITIONS, strict=True)
        result.append(
            Person(
                f"u_{tag}_acc",
                f"demo_{tag}_acc",
                random_fio(rng),
                "preparer",
                rng.weighted(names, weights),
                False,
            )
        )
    return result


def draft_company(seed: int, version: str, i: int, label: str, as_of: date) -> Draft:
    rng = Rng(seed, version, "company", str(i))
    stop = label.startswith("stop_")
    segment = ref.SEGMENTS[ref.STOP_BASE_SEGMENT if stop else label]

    def bucket(factor: str) -> int:
        return draw_bucket(
            rng, segment.main_bucket[factor], ref.BUCKET_COUNTS[factor], segment.p_main
        )

    legal_form = "ooo" if rng.chance(segment.p_ooo) else "ip"
    reporting = legal_form == "ooo" and rng.chance(ref.REPORTING_SHARE_OOO)
    if label == "stop_ebitda":  # §6.1 С3: ООО with reporting
        legal_form, reporting = "ooo", True
    groups = ref.GROUPS
    group = rng.weighted(groups, [g.population_share for g in groups])
    okved = rng.choice(group.okveds)
    turnover = _turnover(rng, legal_form)
    cfads = r1000(turnover * _value(rng, ref.CFADS_SHARE))

    # Factors in the order of §6.3. Age first: it decides the statement length h.
    if label == "stop_young":
        age_months = rng.between(3, 5)
    else:
        age_months = rng.between(*ref.AGE_MONTHS[bucket("business_age_months")])
    registered_at = add_months(as_of, -age_months) - timedelta(
        days=rng.between(*ref.AGE_EXTRA_DAYS)
    )
    months = _statement_months(registered_at, as_of)
    h = len(months)
    window = min(12, h)

    dscr_bucket = bucket("dscr")
    for _ in range(MAX_REDRAWS):
        if dscr_bucket == 0 and rng.chance(ref.DSCR_NO_DEBT_SHARE):
            debt_service = D(0)
            break
        target = _value(rng, ref.DSCR_VALUES[dscr_bucket])
        debt_service = r1(cfads / target)
        got = dscr(cfads, debt_service).value
        if _in_bucket(got, ref.DSCR_BUCKETS[dscr_bucket], upper_closed=False):
            break
    else:
        raise ValueError(f"company {i}: dscr does not land in bucket {dscr_bucket}")

    de_bucket = bucket("debt_to_ebitda")
    report: dict[str, Decimal | None] = {}
    if reporting:
        report = _reporting(rng, group, turnover, window, cfads, debt_service, de_bucket, label)

    tau = None
    trend_bucket = bucket("revenue_trend") if h >= 6 else None  # domain: h < 6 → no trend
    if trend_bucket is not None:
        tau = _value(rng, ref.TREND_VALUES[trend_bucket])
    kappa = _value(rng, ref.CONCENTRATION_VALUES[bucket("counterparty_concentration")])

    bki_bucket = ref.BKI_BUCKETS[bucket("bki_history")]
    if label == "stop_overdue":
        bki_bucket = "current_gt_30"
    tb_bucket = ref.TB_BUCKETS[bucket("transparent_business")]
    overdue = bki_overdue(rng, bki_bucket)
    tb = transparent_business(rng, tb_bucket, can_have_mass_director=legal_form == "ooo")

    low, high = okved.retail_share
    retail = D(0)
    if D(high) > 0:
        retail = min(rng.decimal_between(low, high), 1 - kappa - D("0.05"))
    rest = 1 - kappa - retail
    count = max(rng.between(*ref.OTHER_PAYERS), min_other_payers(kappa, rest, retail > 0))
    weights = [rng.between(*ref.PAYER_WEIGHTS) for _ in range(count)]
    taken: set[str] = set()
    names = counterparty_names(rng, count + 1, taken)
    others = [
        # Without retail the last payer absorbs the monthly rounding; its share stays the same.
        Payer(name, None if (retail == 0 and j == count - 1) else rest * w / sum(weights))
        for j, (name, w) in enumerate(zip(names[1:], weights, strict=True))
    ]
    suppliers = counterparty_names(rng, rng.between(*ref.SUPPLIERS), taken)
    (landlord,) = counterparty_names(rng, 1, taken)
    obligations = _obligations(rng, debt_service, months, registered_at)

    people_rng = Rng(seed, version, "people", str(i))
    staff = _people(people_rng, i, legal_form)
    name = ooo_name(rng, group) if legal_form == "ooo" else ip_name(rng, group, staff[0].fio)

    inputs = CompanyInputs(
        key=f"co_{i:04d}",
        persona=None,
        number=0,  # set in generate_population, by legal form
        legal_form=legal_form,
        group=group,
        okved=okved,
        registered_at=registered_at,
        id_year=registered_at.year,
        name=name,
        address=address(rng),
        registry_status={"stop_liquidating": "liquidating", "stop_liquidated": "liquidated"}.get(
            label, "active"
        ),
        in_egrul=label != "stop_not_in_egrul",
        people=staff,
        months=months,
        window_sum=turnover * window,
        cfads=cfads,
        tau=tau,
        kappa=kappa,
        top_payer=names[0],
        other_payers=others,
        has_retail=retail > 0,
        suppliers=suppliers,
        landlord=landlord,
        obligations=obligations,
        reporting=report,
        bki_overdue=overdue,
        transparent_business=tb,
    )
    return Draft(i, label, inputs, dict(tb["data"]), _latent(seed, version, i, label))


def _reporting(rng, group, turnover, window, cfads, debt_service, de_bucket, label) -> dict:
    """§6.3: reported figures of an ООО (revenue = S_W); debt from the debt/EBITDA bucket."""
    revenue = turnover * window
    cogs = r1(revenue * D(group.cogs_ratio))
    receivables = r1(revenue * rng.between(*ref.RECEIVABLE_DAYS) / 365)
    inventory = r1(cogs * rng.between(*group.dio_days) / 365)
    payables = r1(cogs * rng.between(*ref.PAYABLE_DAYS) / 365)
    ebitda = r1(12 * cfads * _value(rng, ref.EBITDA_FACTOR))
    cash = r1000(turnover * _value(rng, ref.CASH_SHARE))
    if debt_service == 0:
        debt = D(0)  # «долга нет»: the bucket is forced to 0
    else:
        for _ in range(MAX_REDRAWS):
            ratio = _value(rng, ref.DEBT_TO_EBITDA_VALUES[de_bucket])
            debt = r1(ratio * ebitda + cash)
            got = debt_to_ebitda(debt, ebitda, cash).value
            if _in_bucket(got, ref.DEBT_TO_EBITDA_BUCKETS[de_bucket], upper_closed=True):
                break
        else:
            raise ValueError(f"debt/EBITDA does not land in bucket {de_bucket}")
    if label == "stop_ebitda":  # §6.1 С3: EBITDA = 0 (20 %) or −10…100 % of 12 × cfads
        ebitda = D(0) if rng.chance("0.20") else -r1(12 * cfads * _value(rng, ("0.10", "1.00")))
    return {
        "revenue": revenue,
        "cogs": cogs,
        "ebitda": ebitda,
        "debt": debt,
        "cash": cash,
        "receivables": receivables,
        "inventory": inventory,
        "payables": payables,
    }


def _latent(seed: int, version: str, i: int, label: str) -> dict:
    """§6.4: pd = min(0.9, base × exp(0.4 z)); default_12m = u < pd. D9 only."""
    rng = Rng(seed, version, "latent", str(i))
    base = ref.STOP_BASE_PD if label.startswith("stop_") else ref.SEGMENTS[label].base_pd
    pd_float = min(0.9, float(base) * math.exp(0.4 * rng.normal()))
    pd = D(str(pd_float)).quantize(D("0.0001"), rounding=ROUND_HALF_UP)
    u = D(rng.below(1_000_000)) / 1_000_000
    return {"segment": label, "pd": str(pd), "default_12m": u < pd}


def spread_mass_values(seed: int, version: str, drafts: list[Draft]) -> None:
    """§5.2: flagged companies share 3 addresses / 3 director names, at least 2 per value."""
    rng = Rng(seed, version, "mass")
    taken: set[str] = set()
    addresses = []
    while len(addresses) < ref.MASS_VALUES:
        value = address(rng)
        if value not in taken:
            taken.add(value)
            addresses.append(value)
    directors = []
    while len(directors) < ref.MASS_VALUES:
        value = random_fio(rng)
        if value not in directors:
            directors.append(value)
    for flag, values in (("mass_address", addresses), ("mass_director", directors)):
        flagged = [d for d in drafts if d.flags[flag]]
        groups = max(1, min(ref.MASS_VALUES, len(flagged) // 2))
        for j, draft in enumerate(flagged):
            value = values[j % groups]
            if flag == "mass_address":
                draft.inputs.address = value
            else:
                director = draft.inputs.people[0]
                draft.inputs.people[0] = Person(
                    director.key, director.username, value, director.role, director.position,
                    director.login_enabled,
                )  # fmt: skip


def draft_population(seed: int, version: str, n: int, as_of: date) -> list[Draft]:
    segment_labels = labels(Rng(seed, version, "segments"), n)
    drafts = [
        draft_company(seed, version, i, label, as_of)
        for i, label in enumerate(segment_labels, start=1)
    ]
    spread_mass_values(seed, version, drafts)
    counters = {"ip": Counter(POPULATION_FIRST_NUMBER), "ooo": Counter(POPULATION_FIRST_NUMBER)}
    for draft in drafts:
        draft.inputs.number = counters[draft.inputs.legal_form].next()
    return drafts
