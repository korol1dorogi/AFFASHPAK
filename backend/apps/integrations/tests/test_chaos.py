"""XP6: chaos demo — one breaker for every process, a forced outage opens it, the panel sees it."""

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from apps.accounts.demo import seed
from apps.core.testing import assert_matches_contract
from apps.integrations import adapters, flags
from apps.integrations import breaker as breaker_module
from apps.integrations.breaker import OPEN_SECONDS, THRESHOLD, CircuitBreaker, breaker
from apps.pipeline.runner import execute
from apps.pipeline.tests.test_personas import _application, _documents

INN = "000100000170"  # persona 1
PATH = "/api/demo/sources"
pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _clean():
    breaker.reset()
    yield
    breaker.reset()
    flags.reset()


@pytest.fixture
def clock(monkeypatch):
    """Wall clock of the breaker, moved by hand."""
    now = {"t": 1_000_000.0}
    monkeypatch.setattr(breaker_module.time, "time", lambda: now["t"])
    return now


def _bank() -> APIClient:
    client = APIClient()
    client.force_login(get_user_model().objects.get(username="demo_bank"))
    return client


# ── the breaker ──


def test_the_breaker_is_one_for_every_process():
    """Another process is another CircuitBreaker object: it sees the same state (the cache)."""
    for _ in range(THRESHOLD):
        breaker.failure("bki")
    elsewhere = CircuitBreaker()
    assert elsewhere.state("bki").state == "open"
    assert not elsewhere.allow("bki")


def test_three_failures_open_it_then_a_trial_then_a_success_closes_it(clock):
    breaker.failure("bki")
    breaker.failure("bki")
    assert breaker.state("bki").state == "closed"
    assert breaker.state("bki").failures == 2
    breaker.failure("bki")
    state = breaker.state("bki")
    assert (state.state, state.failures) == ("open", 3)
    assert state.open_until == clock["t"] + OPEN_SECONDS
    clock["t"] += OPEN_SECONDS
    assert breaker.state("bki").state == "half_open"
    assert breaker.allow("bki")
    breaker.success("bki")
    assert breaker.state("bki") == breaker_module.BreakerState("closed", 0, None, None)


# ── a forced outage goes through the breaker ──


def test_one_application_with_the_source_off_opens_the_breaker(monkeypatch):
    called: list[str] = []
    real = adapters._answer
    monkeypatch.setattr(
        adapters,
        "_answer",
        lambda source, inn, *, has_account: (
            called.append(source) or real(source, inn, has_account=has_account)
        ),
    )
    flags.set_failing("bki", True)

    answers = adapters.fetch_all(INN, has_account=True)

    assert answers["bki"]["status"] == "unavailable"
    assert "bki" not in called  # the simulator «errors»: no real answer is used
    state = breaker.state("bki")
    assert (state.state, state.failures) == ("open", THRESHOLD)
    assert answers["egrul"]["status"] == "ok"  # the other sources are fine
    assert breaker.state("egrul").state == "closed"


def test_while_open_the_source_is_not_called_at_all(monkeypatch):
    for _ in range(THRESHOLD):
        breaker.failure("bki")
    called: list[str] = []
    monkeypatch.setattr(
        adapters, "_answer", lambda source, inn, *, has_account: called.append(source) or {}
    )
    assert adapters.fetch_all(INN, has_account=True)["bki"]["status"] == "unavailable"
    assert "bki" not in called


def test_a_trial_call_that_succeeds_closes_it(clock):
    for _ in range(THRESHOLD):
        breaker.failure("bki")
    clock["t"] += OPEN_SECONDS
    assert adapters.fetch("bki", INN, has_account=True)["status"] == "ok"
    assert breaker.state("bki").state == "closed"


def test_turning_the_outage_off_closes_the_breaker():
    flags.set_failing("bki", True)
    adapters.fetch_all(INN, has_account=True)
    assert breaker.state("bki").state == "open"
    flags.set_failing("bki", False)
    assert breaker.state("bki").state == "closed"
    assert adapters.fetch_all(INN, has_account=True)["bki"]["status"] == "ok"


def test_scenario_7_still_goes_to_an_officer(settings):
    settings.DEMO_MODE = True
    seed()
    flags.set_failing("bki", True)
    application = _application("demo_coffee_shop", "overdraft_basic", "900000.00", 12)
    _documents(application, tuple(application.product.required_documents))
    execute(application.pk)
    application.refresh_from_db()
    assert application.status == "manual_review"
    assert breaker.state("bki").state == "open"


# ── the demo panel ──


def test_the_panel_sees_the_outage_and_the_open_breaker(settings):
    settings.DEMO_MODE = True
    seed()
    bank = _bank()
    calm = bank.get(PATH)
    assert calm.status_code == 200
    assert_matches_contract(calm, method="get", path=PATH)
    assert [row["source"] for row in calm.json()] == list(flags.SOURCES)
    assert all(row["breaker"]["state"] == "closed" for row in calm.json())
    assert all(row["failing_until"] is None for row in calm.json())

    body = {source: source == "bki" for source in flags.SOURCES}
    bank.put("/api/demo/failures", body, format="json")
    adapters.fetch_all(INN, has_account=True)  # one application meets the outage

    response = bank.get(PATH)
    assert_matches_contract(response, method="get", path=PATH)
    bki = next(row for row in response.json() if row["source"] == "bki")
    assert bki["failing"] is True
    assert bki["failing_until"] is not None
    assert bki["breaker"]["state"] == "open"
    assert bki["breaker"]["failures"] == THRESHOLD
    assert bki["breaker"]["open_until"] is not None
    assert bki["breaker"]["last_failure_at"] is not None


def test_the_panel_is_for_the_bank_on_the_demo_stand_only(settings):
    settings.DEMO_MODE = True
    seed()
    client = APIClient()
    client.force_login(get_user_model().objects.get(username="demo_coffee_shop"))
    forbidden = client.get(PATH)
    assert forbidden.status_code == 403
    assert_matches_contract(forbidden, method="get", path=PATH)
    settings.DEMO_MODE = False
    assert _bank().get(PATH).status_code == 404
