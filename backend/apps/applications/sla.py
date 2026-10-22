"""Bank queue SLA (XP4): how long an application may stay in a status where the bank acts.

Only statuses where the bank or its systems move the application have a norm. Statuses that wait
for the client (info_requested, offer, signing) and the final ones never become overdue: a slow
client is not the bank's delay. Defaults follow what the client is promised in the interface
(«обычно до одного дня» on manual review, «до минуты» for the automatic check, «несколько минут»
for disbursement); settings.APPLICATION_SLA_HOURS overrides them per status.
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from functools import lru_cache

from django.conf import settings
from django.core import checks
from django.db.models import Q

from apps.applications.models import ApplicationStatus

S = ApplicationStatus
logger = logging.getLogger(__name__)

DEFAULT_SLA_HOURS = {
    S.SUBMITTED: 1,
    S.PROCESSING: 1,
    S.MANUAL_REVIEW: 24,
    S.SIGNED: 1,
}


@lru_cache(maxsize=8)
def _parse(raw: str) -> tuple[tuple[tuple[str, int], ...], tuple[str, ...]]:
    """`status=hours,…` → valid overrides and the items that were ignored, with why."""
    overrides: list[tuple[str, int]] = []
    problems: list[str] = []
    for item in (part.strip() for part in raw.split(",")):
        if not item:
            continue
        status, _, value = (piece.strip() for piece in item.partition("="))
        if status not in DEFAULT_SLA_HOURS:
            known = ", ".join(DEFAULT_SLA_HOURS)
            problems.append(f"{item!r}: no norm for this status (only {known})")
        elif not value.isdigit() or int(value) < 1:
            problems.append(f"{item!r}: hours must be a whole number from 1")
        else:
            overrides.append((status, int(value)))
    return tuple(overrides), tuple(problems)


def _configured() -> str:
    return getattr(settings, "APPLICATION_SLA_HOURS", "") or ""


def sla_hours() -> dict[str, int]:
    """Norm in hours by status. A broken SLA_HOURS item is ignored with a warning, never a 500:
    a typo on the stand must not take the bank queue down."""
    overrides, problems = _parse(_configured())
    if problems:
        _warn(problems)
    defaults = {str(status): hours for status, hours in DEFAULT_SLA_HOURS.items()}
    return {**defaults, **dict(overrides)}


@lru_cache(maxsize=8)
def _warn(problems: tuple[str, ...]) -> None:
    """Once per distinct problem set, not on every request."""
    logger.warning("SLA_HOURS ignored, defaults kept: %s", "; ".join(problems))


def check_sla_hours(app_configs, **kwargs) -> list[checks.CheckMessage]:
    """System check: shown by runserver, migrate and `manage.py check` at start."""
    _, problems = _parse(_configured())
    return [
        checks.Warning(
            f"SLA_HOURS {problem} — ignored, the default norm is used",
            hint="Format: SLA_HOURS=manual_review=24,submitted=1 (docs: apps/applications/sla.py)",
            id="applications.W001",
        )
        for problem in problems
    ]


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
