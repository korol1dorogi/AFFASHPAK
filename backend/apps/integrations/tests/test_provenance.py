"""SRC4: provenance of every check — when the answer came, its sha256, the simulator version."""

import json
from datetime import date
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from apps.accounts.demo import seed
from apps.applications.models import BkiConsent, Check
from apps.core.testing import assert_matches_contract
from apps.integrations import adapters
from apps.integrations.breaker import breaker
from apps.integrations.flags import reset
from apps.integrations.provenance import provenance, response_sha256
from apps.pipeline.runner import execute
from apps.pipeline.tests.test_personas import _application, _documents

INN = "000100000170"  # persona 1
VERSION = "datagen-2026.10-v1"
ANSWER = {
    "status": "warning",
    "data": {
        "name": "ООО «Ромашка» (демо)",
        "registered_at": date(2021, 3, 1),
        "share": Decimal("0.80"),
        "flags": ["unreliable_address"],
    },
}


@pytest.fixture(autouse=True)
def _fresh_breaker():
    breaker.reset()
    yield
    breaker.reset()


@pytest.fixture
def seeded(db):
    seed()
    yield
    reset()


# ── the hash ──


def test_the_same_answer_always_has_the_same_hash():
    first = response_sha256(ANSWER)
    assert all(response_sha256(ANSWER) == first for _ in range(100))
    reordered = {"data": dict(reversed(list(ANSWER["data"].items()))), "status": "warning"}
    assert response_sha256(reordered) == first


def test_the_hash_survives_the_round_trip_through_the_database():
    """The pipeline stores data as JSON (dates and decimals as strings): the hash is the same."""
    stored = json.loads(json.dumps(ANSWER["data"], default=str))
    assert response_sha256({"status": "warning", "data": stored}) == response_sha256(ANSWER)


def test_any_change_of_the_answer_changes_the_hash():
    base = response_sha256(ANSWER)
    assert response_sha256({**ANSWER, "status": "ok"}) != base
    changed = {**ANSWER, "data": {**ANSWER["data"], "share": Decimal("0.81")}}
    assert response_sha256(changed) != base


def test_the_hash_is_sha256_of_the_canonical_json():
    """A fixed value: the way of hashing must not change silently (old checks would not match)."""
    # sha256('{"data":{"months":18},"status":"ok"}')
    assert response_sha256({"status": "ok", "data": {"months": 18}}) == (
        "690ed235f402c0f2be908e09f5cb19e36d366ae937588a4cf276b9cf8b4e4a77"
    )
    assert len(response_sha256(ANSWER)) == 64


def test_no_answer_no_provenance():
    assert provenance(adapters.UNAVAILABLE) is None
    assert provenance(adapters.NO_CONSENT) is None
    assert provenance(adapters.NOT_IN_REGISTRY)["response_sha256"] == response_sha256(
        adapters.NOT_IN_REGISTRY
    )  # «no such INN» is an answer of the registry


# ── the adapters ──


@pytest.mark.django_db
def test_every_answer_of_a_persona_carries_its_provenance():
    answers = adapters.fetch_all(INN, has_account=True)
    for source, answer in answers.items():
        found = answer["provenance"]
        assert found["simulator_version"] == VERSION, source
        assert found["response_sha256"] == response_sha256(answer), source
        assert found["received_at"] is not None, source


@pytest.mark.django_db
def test_the_simulator_record_is_not_changed():
    """The record is shared by every request: provenance goes to a copy."""
    adapters.fetch_all(INN, has_account=True)
    assert "provenance" not in adapters.fetch("egrul", INN, has_account=True)


@pytest.mark.django_db
def test_an_outage_and_no_consent_have_no_provenance(monkeypatch):
    monkeypatch.setattr(adapters, "failing_sources", lambda: {"egrul"})
    answers = adapters.fetch_all(INN, has_account=True, bki_consent=False)
    assert answers["egrul"] == {**adapters.UNAVAILABLE, "provenance": None}
    assert answers["bki"] == {**adapters.NO_CONSENT, "provenance": None}
    assert answers["transparent_business"]["provenance"] is not None


# ── stored and shown ──


def _persona_1():
    application = _application("demo_coffee_shop", "overdraft_basic", "900000.00", 12)
    _documents(application, tuple(application.product.required_documents))
    return application


def _bank() -> APIClient:
    client = APIClient()
    client.force_login(get_user_model().objects.get(username="demo_bank"))
    return client


@pytest.mark.django_db
def test_the_pipeline_stores_the_provenance_and_it_is_stable(seeded):
    first, second = _persona_1(), _persona_1()
    execute(first.pk)
    execute(second.pk)

    for check in Check.objects.filter(application=first):
        assert check.simulator_version == VERSION, check.source
        assert check.received_at is not None, check.source
        # What is stored hashes to what was received.
        answer = {"status": check.status, "data": check.data}
        assert check.response_sha256 == response_sha256(answer), check.source
    # The same company, the same answers: the same hashes.
    hashes = {
        application.pk: dict(
            Check.objects.filter(application=application).values_list("source", "response_sha256")
        )
        for application in (first, second)
    }
    assert hashes[first.pk] == hashes[second.pk]


@pytest.mark.django_db
def test_the_bank_card_shows_the_provenance_by_the_contract(seeded):
    application = _persona_1()
    BkiConsent.objects.filter(application=application).delete()
    execute(application.pk)
    path = f"/api/bank/applications/{application.pk}"
    response = _bank().get(path)

    assert response.status_code == 200
    assert_matches_contract(response, method="get", path=path)
    checks = {check["source"]: check for check in response.json()["checks"]}
    assert checks["egrul"]["simulator_version"] == VERSION
    assert len(checks["egrul"]["response_sha256"]) == 64
    assert checks["egrul"]["received_at"]
    # The bureau was not asked: nothing came, nothing to trace.
    assert checks["bki"]["status"] == "consent_missing"
    assert (
        checks["bki"]["received_at"],
        checks["bki"]["response_sha256"],
        checks["bki"]["simulator_version"],
    ) == (None, None, None)
