"""Source outages for the failure scenario (scenario 7). Off unless a test or the demo panel
turns one on. Stored in DemoState so every worker sees the same flags.

An outage lasts FAILURE_TTL from the moment it was turned on, then it is over by itself: a
forgotten «БКИ упал» must not break scenarios 1–6 for the next visitor (fix 6.2).
"""

from datetime import timedelta

from django.utils import timezone

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
    """Turning an outage on again starts its FAILURE_TTL anew (updated_at is auto_now)."""
    if source not in SOURCES:
        raise KeyError(source)
    DemoState.objects.update_or_create(source=source, defaults={"failing": failing})


def reset() -> None:
    DemoState.objects.update(failing=False)
