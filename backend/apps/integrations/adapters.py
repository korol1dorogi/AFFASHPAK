"""Simulated external sources, looked up by INN (demo generator) with retries and a breaker.

S1 will replace the lookup with HTTP. The pipeline only sees status + data.
"""

import logging
from concurrent.futures import ThreadPoolExecutor

from apps.integrations.breaker import breaker
from apps.integrations.flags import SOURCES, failing_sources
from apps.integrations.simulator_data import simulators

ATTEMPTS = 3
UNAVAILABLE = {"status": "unavailable", "data": {}}
NOT_CONNECTED = {"status": "unavailable", "data": {"not_connected": True}}
NOT_IN_REGISTRY = {"status": "failed", "data": {}}
# No consent from the client: the bureau is not asked at all (218-FZ).
NO_CONSENT = {"status": "unavailable", "data": {"consent_missing": True}}
SOURCE_TIMEOUT_SECONDS = 2
logger = logging.getLogger(__name__)


def _answer(source: str, inn: str, *, has_account: bool) -> dict:
    if source == "bank_account":
        if not has_account:
            return dict(NOT_CONNECTED)
        return {"status": "ok", "data": {"months": 18}}
    table = simulators().get(source) or {}
    found = table.get(inn)
    if found is None:
        return dict(NOT_IN_REGISTRY if source == "egrul" else UNAVAILABLE)
    return found


def fetch(source: str, inn: str, *, has_account: bool, failing: bool = False) -> dict:
    """One source. A forced outage or an open breaker is `unavailable` without calling out."""
    if failing or not breaker.allow(source):
        return dict(UNAVAILABLE)
    for attempt in range(1, ATTEMPTS + 1):
        try:
            answer = _answer(source, inn, has_account=has_account)
        except Exception:  # a down simulator is an outage, not a crash of the pipeline
            logger.warning("%s: attempt %s of %s failed", source, attempt, ATTEMPTS, exc_info=True)
            continue
        breaker.success(source)
        return answer
    breaker.failure(source)
    return dict(UNAVAILABLE)


def fetch_all(inn: str, *, has_account: bool, bki_consent: bool = True) -> dict[str, dict]:
    """All four sources at once. A source slower than the timeout counts as unavailable and
    the pipeline does not wait for it (no `with`: its exit would join the slow thread).
    Without the client's consent the credit bureau is never called."""
    failing = failing_sources()  # read once, in the request thread (DemoState lives in the DB)
    simulators()  # build the cached dataset here, once: inside the threads it would hit the timeout
    results: dict[str, dict] = {}
    asked = SOURCES if bki_consent else tuple(s for s in SOURCES if s != "bki")
    if not bki_consent:
        results["bki"] = dict(NO_CONSENT)
    pool = ThreadPoolExecutor(max_workers=len(asked))
    try:
        futures = {
            source: pool.submit(
                fetch, source, inn, has_account=has_account, failing=source in failing
            )
            for source in asked
        }
        for source, future in futures.items():
            try:
                results[source] = future.result(timeout=SOURCE_TIMEOUT_SECONDS)
            except Exception:  # a timeout or a crash of the source: an outage
                breaker.failure(source)
                results[source] = dict(UNAVAILABLE)
    finally:
        pool.shutdown(wait=False, cancel_futures=True)
    return results
