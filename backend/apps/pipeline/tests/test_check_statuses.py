"""SRC2: every check status → the expected outcome. No data is not a decline; no company is."""

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from apps.applications.models import Application, Check
from apps.core.testing import assert_matches_contract
from apps.integrations import adapters
from apps.integrations.breaker import breaker
from apps.pipeline.runner import execute
from apps.pipeline.tests.test_personas import _application, _documents

HIDDEN = {"status": "restricted", "data": {}}


@pytest.fixture(autouse=True)
def _fresh_breaker():
    breaker.reset()
    yield
    breaker.reset()


@pytest.fixture
def answer_with(monkeypatch):
    """Let some sources answer with the given payloads; the others answer as the simulator does."""
    overrides: dict[str, dict] = {}
    real = adapters._answer

    def fake(asked, inn, *, has_account):
        if asked in overrides:
            return dict(overrides[asked])
        return real(asked, inn, has_account=has_account)

    monkeypatch.setattr(adapters, "_answer", fake)

    def install(source: str, payload: dict) -> None:
        overrides[source] = payload

    return install


def _persona_1() -> Application:
    """Persona 1 gets an automatic offer when every source answers (test_personas)."""
    application = _application("demo_coffee_shop", "overdraft_basic", "900000.00", 12)
    _documents(application, tuple(application.product.required_documents))
    return application


def _run(application: Application):
    execute(application.pk)
    application.refresh_from_db()
    return application, application.decisions.get()


def _messages(decision) -> list[str]:
    return [reason["message"] for reason in decision.reasons]


# ── adapters ──


@pytest.mark.django_db
def test_an_inn_missing_from_the_registry_is_not_found():
    assert adapters.fetch("egrul", "0009999999", has_account=True)["status"] == "not_found"


@pytest.mark.django_db
def test_without_consent_the_bureau_is_consent_missing_and_not_asked(monkeypatch):
    asked: list[str] = []
    real = adapters._answer
    monkeypatch.setattr(
        adapters,
        "_answer",
        lambda source, inn, *, has_account: (
            asked.append(source) or real(source, inn, has_account=has_account)
        ),
    )
    answers = adapters.fetch_all("000100000170", has_account=True, bki_consent=False)
    assert answers["bki"]["status"] == "consent_missing"
    assert "bki" not in asked


def test_a_restricted_record_of_the_simulator_passes_as_is(monkeypatch):
    monkeypatch.setattr(adapters, "simulators", lambda: {"bki": {"0001": HIDDEN}})
    assert adapters.fetch("bki", "0001", has_account=True) == HIDDEN


# ── status → outcome ──


@pytest.mark.django_db
def test_not_found_in_the_registry_declines_with_the_reason(seeded, answer_with):
    answer_with("egrul", adapters.NOT_IN_REGISTRY)
    application, decision = _run(_persona_1())

    assert application.status == "declined"
    assert decision.outcome == "declined"
    assert "Компанию не нашли в ЕГРЮЛ/ЕГРИП" in _messages(decision)
    assert decision.improvements == ["Проверьте ИНН компании"]
    check = Check.objects.get(application=application, source="egrul")
    assert (check.status, check.summary) == (
        "not_found",
        "ЕГРЮЛ/ЕГРИП: компания не найдена в реестре",
    )


@pytest.mark.django_db
@pytest.mark.parametrize("source", ["egrul", "transparent_business", "bki"])
def test_restricted_data_goes_to_an_officer_not_to_a_decline(seeded, answer_with, source):
    answer_with(source, HIDDEN)
    application, decision = _run(_persona_1())

    assert application.status == "manual_review"
    assert decision.outcome == "manual_review"
    assert not application.source_unavailable  # the source answered: no outage mark
    assert any("сведения скрыты" in text for text in _messages(decision))
    check = Check.objects.get(application=application, source=source)
    assert check.status == "restricted"
    assert check.summary.endswith("сведения скрыты — проверит сотрудник")


@pytest.mark.django_db
def test_restricted_bureau_scores_neutral_points_with_its_own_text(seeded, answer_with):
    answer_with("bki", HIDDEN)
    application, decision = _run(_persona_1())

    factor = next(f for f in application.score.factors if f["name"] == "bki_history")
    assert factor["value"] is None
    assert "Сведения в БКИ скрыты — историю проверит сотрудник" in _messages(decision)


@pytest.mark.django_db
def test_consent_missing_goes_to_an_officer_without_an_outage_mark(seeded, answer_with):
    application = _persona_1()
    application.bki_consent.delete()
    application, decision = _run(application)

    assert decision.outcome == "manual_review"
    assert not application.source_unavailable
    assert Check.objects.get(application=application, source="bki").status == "consent_missing"
    assert "Нет согласия на запрос в БКИ — историю проверит сотрудник" in _messages(decision)


@pytest.mark.django_db
def test_an_outage_still_raises_source_unavailable(seeded, answer_with):
    answer_with("transparent_business", adapters.UNAVAILABLE)
    application, decision = _run(_persona_1())

    assert decision.outcome == "manual_review"
    assert application.source_unavailable


@pytest.mark.django_db
def test_the_bank_card_with_new_statuses_matches_the_contract(seeded, answer_with):
    # Stop factor С2 declines before scoring, so the card has all three new statuses and no
    # score (a scored card trips over ScoreFactor.value's oneOf — a contract issue apart).
    answer_with("egrul", adapters.NOT_IN_REGISTRY)
    answer_with("transparent_business", HIDDEN)
    application = _persona_1()
    application.bki_consent.delete()
    application, _decision = _run(application)

    client = APIClient()
    client.force_login(get_user_model().objects.get(username="demo_bank"))
    path = f"/api/bank/applications/{application.pk}"
    response = client.get(path)

    assert response.status_code == 200
    assert_matches_contract(response, method="get", path=path)
    statuses = {check["source"]: check["status"] for check in response.json()["checks"]}
    assert statuses == {
        "egrul": "not_found",
        "transparent_business": "restricted",
        "bki": "consent_missing",
        "bank_account": "ok",
    }
