"""Source outages for the failure scenario. Off unless a test or the demo panel turns one on."""

SOURCES = ("egrul", "transparent_business", "bki", "bank_account")

_failing = dict.fromkeys(SOURCES, False)


def is_failing(source: str) -> bool:
    return _failing.get(source, False)


def set_failing(source: str, failing: bool) -> None:
    if source not in _failing:
        raise KeyError(source)
    _failing[source] = failing


def reset() -> None:
    for source in _failing:
        _failing[source] = False
