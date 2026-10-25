"""Simulated sources: retries, circuit breaker, timeout, flags shared through the database."""

import time

import pytest
from rest_framework.test import APIClient

from apps.accounts.demo import seed
from apps.core.testing import assert_matches_contract
from apps.integrations import adapters, flags
from apps.integrations.breaker import THRESHOLD, breaker
from apps.integrations.models import DemoState

INN = "000100000170"  # persona 1
PATH = "/api/demo/failures"
ALL_OFF = {"egrul": False, "transparent_business": False, "bki": False, "bank_account": False}


@pytest.fixture(autouse=True)
def _fresh_breaker():
    breaker.reset()
    yield
    breaker.reset()


@pytest.mark.django_db
def test_all_sources_answer_for_a_persona():
    answers = adapters.fetch_all(INN, has_account=True)
    assert {source: answer["status"] for source, answer in answers.items()} == {
        "egrul": "ok",
        "transparent_business": "ok",
        "bki": "ok",
        "bank_account": "ok",
    }


def test_retries_then_the_breaker_opens(monkeypatch):
    calls = []

    def down(source, inn, *, has_account):
        calls.append(source)
        raise ConnectionError("simulator down")

    monkeypatch.setattr(adapters, "_answer", down)
    # Every failed call counts (XP6): the three retries of one request open the breaker.
    assert adapters.fetch("bki", INN, has_account=True)["status"] == "unavailable"
    assert len(calls) == adapters.ATTEMPTS == THRESHOLD
    assert not breaker.allow("bki")
    assert adapters.fetch("bki", INN, has_account=True)["status"] == "unavailable"
    assert len(calls) == THRESHOLD  # open breaker: no more calls


@pytest.mark.django_db
def test_a_slow_source_does_not_hold_the_pipeline(monkeypatch):
    real = adapters._answer

    def slow_bki(source, inn, *, has_account):
        if source == "bki":
            time.sleep(adapters.SOURCE_TIMEOUT_SECONDS + 3)
        return real(source, inn, has_account=has_account)

    monkeypatch.setattr(adapters, "_answer", slow_bki)
    started = time.monotonic()
    answers = adapters.fetch_all(INN, has_account=True)
    assert time.monotonic() - started < adapters.SOURCE_TIMEOUT_SECONDS + 1.5
    assert answers["bki"]["status"] == "unavailable"
    assert answers["egrul"]["status"] == "ok"


@pytest.mark.django_db
def test_flags_live_in_the_database():
    flags.set_failing("bki", True)
    assert DemoState.objects.get(source="bki").failing is True
    assert flags.current()["bki"] is True
    assert adapters.fetch_all(INN, has_account=True)["bki"]["status"] == "unavailable"
    flags.reset()
    assert flags.current() == ALL_OFF


@pytest.mark.django_db
def test_failures_api_bank_only_and_by_contract(settings):
    settings.DEMO_MODE = True
    seed()
    bank, client = APIClient(), APIClient()
    bank.post("/api/demo/login", {"persona": "bank"}, format="json")
    client.post("/api/demo/login", {"persona": "coffee_shop"}, format="json")

    response = bank.get(PATH)
    assert response.status_code == 200
    assert_matches_contract(response, method="get", path=PATH)
    body = {**ALL_OFF, "bki": True}
    response = bank.put(PATH, body, format="json")
    assert response.status_code == 200
    assert_matches_contract(response, method="put", path=PATH, request_body=body)
    assert response.json() == body

    assert client.get(PATH).status_code == 403
    assert APIClient().get(PATH).status_code == 401
    assert bank.put(PATH, {"bki": True}, format="json").status_code == 400
    assert bank.put(PATH, {**ALL_OFF, "sms": True}, format="json").status_code == 400
    flags.reset()


@pytest.mark.django_db
def test_failures_api_does_not_exist_without_demo_mode(settings):
    settings.DEMO_MODE = False
    assert APIClient().get(PATH).status_code == 404
