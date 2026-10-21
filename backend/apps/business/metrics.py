"""Key metrics of a company for the client (GET /api/company/metrics, CompanyMetrics).

No formulas here: the scorecard's financial factors compute them through apps/credit_math and
already explain themselves as Reason (metric, value, threshold, passed, message). Checks of
external sources (BKI, «Прозрачный бизнес») are not part of the profile: they run per application.
"""

from django.utils import timezone

from apps.business.models import Company, FinancialSnapshot
from apps.credit_math import Reason
from apps.scoring import CURRENT_MODEL_VERSION, build_input, get_scorecard
from apps.scoring.factors import (
    business_age_factor,
    counterparty_concentration_factor,
    debt_to_ebitda_factor,
    dscr_factor,
    revenue_trend_factor,
)
from apps.scoring.inputs import SNAPSHOT_FIELDS


def latest_snapshot(company: Company) -> FinancialSnapshot | None:
    return company.snapshots.first()  # Meta.ordering: newest period first


def company_metrics(company: Company, snapshot: FinancialSnapshot | None) -> list[Reason]:
    inp = build_input(
        {
            "legal_form": company.legal_form,
            "registry_status": company.registry_status,
            "registered_at": company.registered_at,
        },
        {name: getattr(snapshot, name) for name in SNAPSHOT_FIELDS} if snapshot else None,
        {},
        on_date=timezone.localdate(),
    )
    card = get_scorecard(CURRENT_MODEL_VERSION)
    factors = (
        business_age_factor(inp, card),
        dscr_factor(inp, card),
        debt_to_ebitda_factor(inp, card),
        revenue_trend_factor(inp, card),
        counterparty_concentration_factor(inp, card),
    )
    return [factor.as_reason() for factor in factors]
