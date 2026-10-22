"""Bank queue SLA (XP4): how long an application may stay in a status where the bank acts.

Only statuses where the bank or its systems move the application have a norm. Statuses that wait
for the client (info_requested, offer, signing) and the final ones never become overdue: a slow
client is not the bank's delay. Defaults follow what the client is promised in the interface
(«обычно до одного дня» on manual review, «до минуты» for the automatic check, «несколько минут»
for disbursement); settings.APPLICATION_SLA_HOURS overrides them per status.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta

from django.conf import settings
from django.db.models import Q

from apps.applications.models import ApplicationStatus

S = ApplicationStatus

DEFAULT_SLA_HOURS = {
    S.SUBMITTED: 1,
    S.PROCESSING: 1,
    S.MANUAL_REVIEW: 24,
    S.SIGNED: 1,
}


def sla_hours() -> dict[str, int]:
    """Norm in hours by status; settings may change the defaults but not add client statuses."""
    hours = {str(status): value for status, value in DEFAULT_SLA_HOURS.items()}
    for status, value in getattr(settings, "APPLICATION_SLA_HOURS", {}).items():
        if status not in hours:
            raise ValueError(f"SLA_HOURS: no norm can be set for status {status!r}")
        if value < 1:
            raise ValueError(f"SLA_HOURS: {status} must be at least 1 hour")
        hours[status] = value
    return hours


@dataclass(frozen=True)
class SlaState:
    due_at: datetime | None
    is_overdue: bool
    overdue_hours: int


def sla_state(status: str, status_changed_at: datetime, now: datetime) -> SlaState:
    """Due time from entering the current status; overdue strictly after it."""
    hours = sla_hours().get(status)
    if hours is None:
        return SlaState(None, False, 0)
    due_at = status_changed_at + timedelta(hours=hours)
    if now <= due_at:
        return SlaState(due_at, False, 0)
    return SlaState(due_at, True, int((now - due_at).total_seconds()) // 3600)


def overdue_q(now: datetime) -> Q:
    """Applications past their status norm at `now`, as one database filter."""
    condition = Q(pk__in=[])
    for status, hours in sla_hours().items():
        condition |= Q(status=status, status_changed_at__lt=now - timedelta(hours=hours))
    return condition


def open_q() -> Q:
    """Applications in a status that has a norm."""
    return Q(status__in=list(sla_hours()))
