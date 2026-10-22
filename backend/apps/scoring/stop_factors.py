"""Stop factors С1–С5 (decision-model.md §2): found here, acted upon by the decision rules (L4).

Works on partial input too: at validation there are no checks yet, so only С1 (by Company) and С5
are visible; С1 is checked again on the ЕГРЮЛ answer at enrichment.
"""

from dataclasses import dataclass
from decimal import Decimal

from apps.credit_math import Reason
from apps.scoring import texts
from apps.scoring.age import business_age_months
from apps.scoring.inputs import ScoringInput
from apps.scoring.policy import CURRENT_POLICY_VERSION, get_policy

LIQUIDATION = {
    "liquidating": "По данным ЕГРЮЛ компания в процессе ликвидации — кредит оформить нельзя",
    "liquidated": "По данным ЕГРЮЛ компания ликвидирована — кредит оформить нельзя",
}


@dataclass(frozen=True)
class StopFactor:
    code: str  # «С1»…«С5»
    reason: Reason
    improvement: str | None


def _liquidation(inp: ScoringInput) -> StopFactor | None:
    egrul = inp.check("egrul")
    statuses = [inp.registry_status]
    if egrul is not None and not egrul.has_no_data:
        statuses.append(egrul.data.get("registry_status"))
    status = next((s for s in statuses if s in LIQUIDATION), None)
    if status is None:
        return None
    return StopFactor("С1", Reason("registry_status", None, None, False, LIQUIDATION[status]), None)


def _not_in_registry(inp: ScoringInput) -> StopFactor | None:
    egrul = inp.check("egrul")
    # not_found since SRC2; failed is how the registry said it before (old checks, fixtures).
    if egrul is None or egrul.status not in {"not_found", "failed"}:
        return None
    reason = Reason("egrul_found", None, None, False, "Компанию не нашли в ЕГРЮЛ/ЕГРИП")
    return StopFactor("С2", reason, "Проверьте ИНН компании")


def _no_operating_profit(inp: ScoringInput) -> StopFactor | None:
    ebitda = inp.metric("ebitda")
    if ebitda is None or ebitda > 0:
        return None
    reason = Reason(
        "ebitda", ebitda, Decimal(0), False,
        "Операционная прибыль за год ≤ 0: бизнесу нечем обслуживать долг",
    )  # fmt: skip
    return StopFactor("С3", reason, "Подайте заявку, когда бизнес выйдет на операционную прибыль")


def _current_overdue(inp: ScoringInput, limit: int) -> StopFactor | None:
    bki = inp.check("bki")
    if bki is None or bki.has_no_data:
        return None
    current = int(bki.data["current_overdue_days"])
    if current <= limit:
        return None
    reason = Reason(
        "bki_current_overdue_days", Decimal(current), Decimal(limit), False,
        f"Сейчас есть просрочка по кредиту больше {texts.days(limit)}",
    )  # fmt: skip
    return StopFactor("С4", reason, "Погасите текущую просрочку и подайте заявку снова")


def _too_young(inp: ScoringInput, minimum: int) -> StopFactor | None:
    if inp.registered_at is None:  # cannot be checked: manual review (П3), not a decline
        return None
    age = business_age_months(inp.registered_at, inp.on_date)
    if age >= minimum:
        return None
    reason = Reason(
        "business_age_months", Decimal(age), Decimal(minimum), False,
        f"Бизнесу {age} мес, а продукт требует от {minimum}",
    )  # fmt: skip
    return StopFactor(
        "С5",
        reason,
        f"Вернитесь, когда бизнесу будет {minimum} месяцев: с даты регистрации прошло {age} мес",
    )


def stop_factors(
    inp: ScoringInput, policy_version: str = CURRENT_POLICY_VERSION
) -> list[StopFactor]:
    """All stop factors found, in С1…С5 order; empty list — none."""
    policy = get_policy(policy_version)
    found = (
        _liquidation(inp),
        _not_in_registry(inp),
        _no_operating_profit(inp),
        _current_overdue(inp, policy.stop_current_overdue_days),
        _too_young(inp, policy.stop_min_business_age_months),
    )
    return [stop for stop in found if stop is not None]
