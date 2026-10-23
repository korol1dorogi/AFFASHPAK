"""Source outages for the failure scenario (scenario 7). Off unless a test or the demo panel
turns one on. Stored in DemoState so every worker sees the same flags.

An outage lasts FAILURE_TTL from the moment it was turned on, then it is over by itself: a
forgotten «БКИ упал» must not break scenarios 1–6 for the next visitor (fix 6.2).
"""

from datetime import UTC, datetime, timedelta

from django.utils import timezone

from apps.integrations.breaker import breaker
from apps.integrations.models import DemoState

SOURCES = ("egrul", "transparent_business", "bki", "bank_account")
FAILURE_TTL = timedelta(minutes=15)


def failing_sources() -> set[str]:
    since = timezone.now() - FAILURE_TTL
    return set(
        DemoState.objects.filter(failing=True, updated_at__gt=since).values_list(
            "source", flat=True
        )
    )


def is_failing(source: str) -> bool:
    return source in failing_sources()


def current() -> dict[str, bool]:
    failing = failing_sources()
    return {source: source in failing for source in SOURCES}


def set_failing(source: str, failing: bool) -> None:
    """Turning an outage on again starts its FAILURE_TTL anew (updated_at is auto_now).
    Turning it off also closes the source's breaker: the operator fixed the source, the next
    scenario must not wait OPEN_SECONDS for a trial call (XP6)."""
    if source not in SOURCES:
        raise KeyError(source)
    DemoState.objects.update_or_create(source=source, defaults={"failing": failing})
    if not failing:
        breaker.reset(source)


def _moment(epoch: float | None) -> datetime | None:
    return None if epoch is None else datetime.fromtimestamp(epoch, tz=UTC)


def overview() -> list[dict]:
    """Every source for the demo panel (XP6, DemoSource): the outage with the moment it ends by
    itself, and the circuit breaker — state, failed calls in a row, until when it stays open."""
    rows = {row.source: row for row in DemoState.objects.filter(source__in=SOURCES)}
    failing = failing_sources()
    result = []
    for source in SOURCES:
        state = breaker.state(source)
        result.append(
            {
                "source": source,
                "failing": source in failing,
                "failing_until": (
                    rows[source].updated_at + FAILURE_TTL if source in failing else None
                ),
                "breaker": {
                    "state": state.state,
                    "failures": state.failures,
                    "open_until": _moment(state.open_until),
                    "last_failure_at": _moment(state.last_failure_at),
                },
            }
        )
    return result


def reset() -> None:
    DemoState.objects.update(failing=False)
