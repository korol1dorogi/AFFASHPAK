"""Simulated external sources, looked up by INN (demo generator) with retries and a breaker.

S1 will replace the lookup with HTTP. The pipeline only sees status + data.
"""

from concurrent.futures import ThreadPoolExecutor
from functools import cache

from apps.demo_data.build import generate
from apps.integrations.breaker import breaker
from apps.integrations.flags import SOURCES, is_failing

ATTEMPTS = 3
UNAVAILABLE = {"status": "unavailable", "data": {}}
NOT_IN_REGISTRY = {"status": "failed", "data": {}}
SOURCE_TIMEOUT_SECONDS = 2


@cache
def _simulators() -> dict:
    return generate(n_companies=0)["simulators"]


def _answer(source: str, inn: str, *, has_account: bool) -> dict:
    if source == "bank_account":
        if not has_account:
            return dict(UNAVAILABLE)
        return {"status": "ok", "data": {"months": 18}}
    table = _simulators().get(source) or {}
    found = table.get(inn)
    if found is None:
        return dict(NOT_IN_REGISTRY if source == "egrul" else UNAVAILABLE)
    return found


def fetch(source: str, inn: str, *, has_account: bool) -> dict:
    """One source. A forced outage or an open breaker is `unavailable` without calling out."""
    if is_failing(source) or not breaker.allow(source):
        return dict(UNAVAILABLE)
    last_error: Exception | None = None
    for _ in range(ATTEMPTS):
        try:
            answer = _answer(source, inn, has_account=has_account)
        except Exception as exc:  # a down simulator is an outage, not a crash of the pipeline
            last_error = exc
            continue
        breaker.success(source)
        return answer
    breaker.failure(source)
    if last_error is not None:
        return dict(UNAVAILABLE)
    return dict(UNAVAILABLE)


def fetch_all(inn: str, *, has_account: bool) -> dict[str, dict]:
    """All four sources at once. One slow source does not block the others past the timeout."""
    results: dict[str, dict] = {}
    with ThreadPoolExecutor(max_workers=len(SOURCES)) as pool:
        futures = {
            pool.submit(fetch, source, inn, has_account=has_account): source for source in SOURCES
        }
        for future, source in futures.items():
            try:
                results[source] = future.result(timeout=SOURCE_TIMEOUT_SECONDS)
            except Exception:
                breaker.failure(source)
                results[source] = dict(UNAVAILABLE)
    return results
