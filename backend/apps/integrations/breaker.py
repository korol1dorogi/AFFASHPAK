"""Per-source circuit breaker. Three failures open it; a success closes it."""

import time

THRESHOLD = 3
OPEN_SECONDS = 30.0


class CircuitBreaker:
    def __init__(self) -> None:
        self._failures: dict[str, int] = {}
        self._open_until: dict[str, float] = {}

    def allow(self, source: str) -> bool:
        until = self._open_until.get(source)
        return until is None or time.monotonic() >= until

    def success(self, source: str) -> None:
        self._failures[source] = 0
        self._open_until.pop(source, None)

    def failure(self, source: str) -> None:
        count = self._failures.get(source, 0) + 1
        self._failures[source] = count
        if count >= THRESHOLD:
            self._open_until[source] = time.monotonic() + OPEN_SECONDS

    def reset(self) -> None:
        self._failures.clear()
        self._open_until.clear()


breaker = CircuitBreaker()
