"""Registry marks that need an officer, not a decline (SRC5): unreliable address or director,
pending exclusion from ЕГРЮЛ. The scorecard is not touched; the decision rules (L4) send the
application to manual review with these reasons.
"""

from apps.credit_math import Reason
from apps.scoring.inputs import ScoringInput

REGISTRY_MARKS = {
    "unreliable_address": "В ЕГРЮЛ есть отметка, что адрес компании недостоверен",
    "unreliable_director": "В ЕГРЮЛ есть отметка, что сведения о руководителе недостоверны",
    "pending_exclusion": "ФНС готовит исключение компании из ЕГРЮЛ",
}
OFFICER = ", поэтому заявку проверит сотрудник банка. Это не отказ"


def review_reasons(inp: ScoringInput) -> list[Reason]:
    """Reasons for manual review in REGISTRY_MARKS order; empty — nothing to look at.
    Hidden, missing or not found registry data is handled elsewhere (SRC2), not read here."""
    egrul = inp.check("egrul")
    if egrul is None or egrul.has_no_data or egrul.status in {"not_found", "failed"}:
        return []
    return [
        Reason(f"egrul_{mark}", None, None, False, text + OFFICER)
        for mark, text in REGISTRY_MARKS.items()
        if egrul.data.get(mark)
    ]
