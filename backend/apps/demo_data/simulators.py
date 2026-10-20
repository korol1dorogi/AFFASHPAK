"""Simulator answers by INN: egrul, transparent_business, bki (docs/data-spec.md §5).

`status` is the Check.status the answer leads to (§5.1); `data` keys are those of D4 §1 plus the
S1-only keys of §5.1. bank_account is not duplicated: S1 reads statements[] and snapshots.
"""

from datetime import date
from decimal import Decimal

from apps.demo_data.amounts import add_months, money, r1
from apps.demo_data.reference import TAX_ARREARS
from apps.demo_data.rng import Rng
from apps.demo_data.statements import Obligation

BKI_PAST_LE_30 = (1, 30)
BKI_PAST_GT_30 = (31, 120)
BKI_CURRENT_1_30 = (1, 30)
BKI_CURRENT_GT_30 = (31, 90)
BKI_PAST_WITH_CURRENT = (0, 60)


def egrul(company: dict, founders: list[dict]) -> dict:
    active = company["registry_status"] == "active"
    return {
        "status": "ok" if active else "warning",
        "data": {
            "registry_status": company["registry_status"],
            "registered_at": company["registered_at"],
            "okved": company["okved"],
            "okved_name": company["okved_name"],
            "address": company["address"],
            "director_name": company["director_name"],
            "founders": founders,
        },
    }


def transparent_business(rng: Rng, bucket: str, *, can_have_mass_director: bool) -> dict:
    """§5.2 buckets: no_flags · one_flag · debt_or_both.

    An ИП has no mass_director (the director is the entrepreneur): one flag is always
    mass_address, and debt_or_both is always the tax debt, so it still scores 0 as in D4.
    """
    mass_address = mass_director = False
    arrears = Decimal(0)
    if bucket == "one_flag":
        mass_director = can_have_mass_director and rng.chance("0.5")
        mass_address = not mass_director
    elif bucket == "debt_or_both":
        if not can_have_mass_director or rng.chance("0.7"):
            arrears = Decimal(rng.between(*TAX_ARREARS))
        else:
            mass_address = mass_director = True
    elif bucket != "no_flags":
        raise ValueError(f"unknown transparent_business bucket: {bucket}")
    return tb_answer(mass_address, mass_director, arrears)


def tb_answer(mass_address: bool, mass_director: bool, tax_arrears: Decimal) -> dict:
    flagged = mass_address or mass_director or tax_arrears > 0
    return {
        "status": "warning" if flagged else "ok",
        "data": {
            "mass_address": mass_address,
            "mass_director": mass_director,
            "tax_arrears": money(tax_arrears),
        },
    }


def bki_overdue(rng: Rng, bucket: str) -> tuple[int, int]:
    """(current_overdue_days, past_overdue_max_days) for a §5.2 bucket."""
    if bucket == "clean":
        return 0, 0
    if bucket == "past_le_30":
        return 0, rng.between(*BKI_PAST_LE_30)
    if bucket == "past_gt_30":
        return 0, rng.between(*BKI_PAST_GT_30)
    if bucket == "current_1_30":
        current = rng.between(*BKI_CURRENT_1_30)
        return current, max(current, rng.between(*BKI_PAST_WITH_CURRENT))
    if bucket == "current_gt_30":
        current = rng.between(*BKI_CURRENT_GT_30)
        return current, current
    raise ValueError(f"unknown bki bucket: {bucket}")


def bki_status(current: int, past: int) -> str:
    if current > 30:
        return "failed"
    if current > 0 or past > 30:
        return "warning"
    return "ok"


def obligation_balances(
    rng: Rng, obligations: list[Obligation], remaining: tuple[int, int], debt: Decimal | None
) -> list[Decimal]:
    """balance = payment × remaining months; with reporting the balances sum up to `debt`."""
    balances = [o.monthly_payment * rng.between(*remaining) for o in obligations]
    if debt is None or not obligations:
        return balances
    total = sum(balances)
    scaled = [r1(b * debt / total) for b in balances[:-1]]
    scaled.append(debt - sum(scaled))
    if min(scaled) <= 0:
        raise ValueError("cannot scale obligation balances to the reported debt")
    return scaled


def bki(current: int, past: int, obligations: list[Obligation], balances: list[Decimal]) -> dict:
    return {
        "status": bki_status(current, past),
        "data": {
            "current_overdue_days": current,
            "past_overdue_max_days": past,
            "obligations": [
                {
                    "kind": o.kind,
                    "monthly_payment": money(o.monthly_payment),
                    "balance": money(balance),
                    "opened_at": o.opened_at.isoformat(),
                }
                for o, balance in zip(obligations, balances, strict=True)
            ],
        },
    }


def unavailable() -> dict:
    """A source that does not answer (§5.1): status unavailable, empty data."""
    return {"status": "unavailable", "data": {}}


def opened_before(
    rng: Rng, period_from: date, registered_at: date, months: tuple[int, int]
) -> date:
    """Opening date of an obligation that predates the statement, not before registration."""
    first = max(registered_at.toordinal(), add_months(period_from, -months[1]).toordinal())
    last = period_from.toordinal() - 1
    if last < first:
        raise ValueError("the business is too young for an obligation opened before the statement")
    return date.fromordinal(rng.between(first, last))
