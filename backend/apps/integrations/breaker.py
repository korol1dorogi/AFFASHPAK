"""Per-source circuit breaker. Three failed calls in a row open it for OPEN_SECONDS; after that
one trial call goes through (half-open); a success closes it.

The state lives in the Django cache — on the stand a table in PostgreSQL (settings.CACHES) —
so every gunicorn worker, the Celery worker and the demo panel see the same breaker (XP6).
Wall-clock time, not monotonic: the processes do not share a clock origin.
"""

import time
from dataclasses import dataclass

from django.core.cache import cache

THRESHOLD = 3
OPEN_SECONDS = 30.0
KEY = "breaker:{}"


@dataclass(frozen=True)
class BreakerState:
    state: str  # closed | open | half_open
    failures: int
    open_until: float | None  # epoch seconds
    last_failure_at: float | None


class CircuitBreaker:
    def _load(self, source: str) -> dict:
        return cache.get(KEY.format(source)) or {"failures": 0, "open_until": None, "last": None}

    def allow(self, source: str) -> bool:
        until = self._load(source)["open_until"]
        return until is None or time.time() >= until

    def success(self, source: str) -> None:
        cache.delete(KEY.format(source))

    def failure(self, source: str) -> None:
        data = self._load(source)
        data["failures"] += 1
        data["last"] = time.time()
        if data["failures"] >= THRESHOLD:
            data["open_until"] = data["last"] + OPEN_SECONDS
        cache.set(KEY.format(source), data, timeout=None)

    def state(self, source: str) -> BreakerState:
        data = self._load(source)
        until = data["open_until"]
        if until is None:
            name = "closed"
        elif time.time() < until:
            name = "open"
        else:
            name = "half_open"  # the next call is a trial
        return BreakerState(name, data["failures"], until, data["last"])

    def reset(self, source: str | None = None) -> None:
        from apps.integrations.flags import SOURCES

        cache.delete_many([KEY.format(s) for s in ([source] if source else SOURCES)])


breaker = CircuitBreaker()
