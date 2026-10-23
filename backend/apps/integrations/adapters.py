"""Simulated external sources, looked up by INN (demo generator) with retries and a breaker.

S1 will replace the lookup with HTTP. The pipeline only sees status + data. Statuses (SRC2):
ok, warning, failed — the source answered; unavailable — it did not; not_found — the registry
has no such INN; restricted — the source answered but hid the data (a simulator record may
carry it as is); consent_missing — the credit bureau was not asked at all.
`fetch_all` adds `provenance` to every answer (SRC4): when it came, its sha256 and the
simulator version, None when the source did not answer.
"""

import logging
from concurrent.futures import ThreadPoolExecutor

from apps.integrations.breaker import THRESHOLD, breaker
from apps.integrations.flags import SOURCES, failing_sources
from apps.integrations.provenance import provenance
from apps.integrations.simulator_data import simulators

ATTEMPTS = 3
UNAVAILABLE = {"status": "unavailable", "data": {}}
NOT_CONNECTED = {"status": "unavailable", "data": {"not_connected": True}}
NOT_IN_REGISTRY = {"status": "not_found", "data": {}}
# No consent from the client: the bureau is not asked at all (218-FZ).
NO_CONSENT = {"status": "consent_missing", "data": {"consent_missing": True}}
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


class SimulatedOutage(ConnectionError):
    """The demo panel turned the source off: the simulator «answers» with an error (XP6)."""


def _attempts(source: str) -> int:
    """How many calls the breaker lets through now: none while open, one trial when half-open,
    otherwise up to ATTEMPTS but no more than it takes to open it."""
    state = breaker.state(source)
    if state.state == "open":
        return 0
    if state.state == "half_open":
        return 1
    return max(1, min(ATTEMPTS, THRESHOLD - state.failures))


def _call(
    source: str, inn: str, *, has_account: bool, failing: bool, attempts: int
) -> tuple[dict | None, int]:
    """Up to `attempts` calls: (the answer or None, failed calls). No database here: it runs in a
    worker thread of fetch_all, the breaker is read and written by the calling thread."""
    failed = 0
    for attempt in range(1, attempts + 1):
        try:
            if failing:
                raise SimulatedOutage(f"{source} is turned off on the demo panel")
            return _answer(source, inn, has_account=has_account), failed
        except Exception:  # a down simulator is an outage, not a crash of the pipeline
            failed += 1
            logger.warning("%s: attempt %s of %s failed", source, attempt, attempts, exc_info=True)
    return None, failed


def _settle(source: str, answer: dict | None, failed: int) -> None:
    """Every failed call counts for the breaker — a forced outage too, so one application opens
    it (XP6); an answer closes it."""
    for _ in range(failed):
        breaker.failure(source)
    if answer is not None:
        breaker.success(source)


def fetch(source: str, inn: str, *, has_account: bool, failing: bool = False) -> dict:
    """One source. An open breaker is `unavailable` without calling out."""
    attempts = _attempts(source)
    answer, failed = _call(source, inn, has_account=has_account, failing=failing, attempts=attempts)
    _settle(source, answer, failed)
    return dict(UNAVAILABLE) if answer is None else answer


def _with_provenance(answer: dict) -> dict:
    """A new dict: the simulator's record is shared (cached), it must not be changed."""
    return {**answer, "provenance": provenance(answer)}


def _fetched(source: str, inn: str, *, has_account: bool, failing: bool, attempts: int):
    """In the worker thread, so `received_at` is the moment the answer came."""
    answer, failed = _call(source, inn, has_account=has_account, failing=failing, attempts=attempts)
    return (None if answer is None else _with_provenance(answer)), failed


def fetch_all(inn: str, *, has_account: bool, bki_consent: bool = True) -> dict[str, dict]:
    """All four sources at once. A source slower than the timeout counts as unavailable and
    the pipeline does not wait for it (no `with`: its exit would join the slow thread).
    Without the client's consent the credit bureau is never called."""
    failing = failing_sources()  # read once, in the request thread (DemoState lives in the DB)
    simulators()  # build the cached dataset here, once: inside the threads it would hit the timeout
    results: dict[str, dict] = {}
    asked = SOURCES if bki_consent else tuple(s for s in SOURCES if s != "bki")
    if not bki_consent:
        results["bki"] = _with_provenance(NO_CONSENT)
    attempts = {source: _attempts(source) for source in asked}  # the breaker: this thread only
    pool = ThreadPoolExecutor(max_workers=len(asked))
    try:
        futures = {
            source: pool.submit(
                _fetched,
                source,
                inn,
                has_account=has_account,
                failing=source in failing,
                attempts=attempts[source],
            )
            for source in asked
        }
        for source, future in futures.items():
            try:
                answer, failed = future.result(timeout=SOURCE_TIMEOUT_SECONDS)
            except Exception:  # a timeout or a crash of the source: an outage
                answer, failed = None, 1
            _settle(source, answer, failed)
            results[source] = _with_provenance(UNAVAILABLE) if answer is None else answer
    finally:
        pool.shutdown(wait=False, cancel_futures=True)
    return results
