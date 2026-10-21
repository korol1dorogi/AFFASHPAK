"""Source outages for the failure scenario (scenario 7). Off unless a test or the demo panel
turns one on. Stored in DemoState so every worker sees the same flags."""

from apps.integrations.models import DemoState

SOURCES = ("egrul", "transparent_business", "bki", "bank_account")


def failing_sources() -> set[str]:
    return set(DemoState.objects.filter(failing=True).values_list("source", flat=True))


def is_failing(source: str) -> bool:
    return source in failing_sources()


def current() -> dict[str, bool]:
    failing = failing_sources()
    return {source: source in failing for source in SOURCES}


def set_failing(source: str, failing: bool) -> None:
    if source not in SOURCES:
        raise KeyError(source)
    DemoState.objects.update_or_create(source=source, defaults={"failing": failing})


def reset() -> None:
    DemoState.objects.update(failing=False)
