"""XP2 through the pipeline and the API: the plan reaches the client only for a decline by grade."""

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from apps.applications.models import Decision
from apps.applications.serializers import DecisionSerializer
from apps.core.testing import assert_matches_contract
from apps.integrations.breaker import breaker
from apps.pipeline.runner import execute
from apps.pipeline.tests.test_personas import _application, _documents


@pytest.fixture(autouse=True)
def _fresh_breaker():
    breaker.reset()
    yield
    breaker.reset()


def _client(username: str) -> APIClient:
    client = APIClient()
    client.force_login(get_user_model().objects.get(username=username))
    return client


def _persona_5():
    application = _application(
        "demo_dependent_supplier",
        "working_capital_loan_basic",
        "3000000.00",
        12,
        need_type="working_capital",
    )
    _documents(application, ("bank_statement", "tax_return"))
    execute(application.pk)
    return application


@pytest.mark.django_db
def test_persona_5_sees_two_steps_to_grade_c(seeded):
    application = _persona_5()
    path = f"/api/applications/{application.pk}"
    response = _client("demo_dependent_supplier").get(path)

    assert response.status_code == 200
    assert_matches_contract(response, method="get", path=path)
    decision = response.json()["decision"]
    assert (decision["outcome"], decision["grade"]) == ("declined", "E")
    assert decision["approval_plan"] == {
        "current_total": 47,
        "target_total": 60,
        "target_grade": "C",
        "steps": [
            {
                "metric": "counterparty_concentration",
                "current": "0.8000",
                "target": "0.5",
                "points": 7,
                "message": (
                    "Найдите ещё покупателей, чтобы на крупнейшего приходилось "
                    "не больше 50% поступлений (сейчас 80%)"
                ),
            },
            {
                "metric": "revenue_trend",
                "current": "0.8000",
                "target": "0.9",
                "points": 6,
                "message": "Верните выручку хотя бы к 90% от прошлого года (сейчас 80%)",
            },
        ],
    }
    assert len(decision["improvements"]) == 4  # the general advice stays as it was


@pytest.mark.django_db
def test_the_bank_card_carries_the_plan_and_matches_the_contract(seeded):
    application = _persona_5()
    path = f"/api/bank/applications/{application.pk}"
    response = _client("demo_bank").get(path)
    assert response.status_code == 200
    assert_matches_contract(response, method="get", path=path)
    assert response.json()["decisions"][0]["approval_plan"]["target_grade"] == "C"


@pytest.mark.django_db
def test_a_stop_factor_has_no_plan(seeded):
    application = _application("demo_liquidating_company", "overdraft_basic", "500000.00", 6)
    _documents(application, tuple(application.product.required_documents))
    execute(application.pk)
    decision = application.decisions.get()
    assert (decision.outcome, decision.grade) == ("declined", None)
    assert DecisionSerializer(decision).data["approval_plan"] is None


@pytest.mark.django_db
def test_an_offer_has_no_plan(seeded):
    application = _application("demo_coffee_shop", "overdraft_basic", "900000.00", 12)
    _documents(application, tuple(application.product.required_documents))
    execute(application.pk)
    assert DecisionSerializer(application.decisions.get()).data["approval_plan"] is None


@pytest.mark.django_db
def test_an_officers_decline_has_no_plan(seeded):
    application = _persona_5()
    auto = application.decisions.get()
    officer = Decision.objects.create(
        application=application,
        outcome="declined",
        decided_by="officer",
        grade=auto.grade,
        policy_version="officer",
        reasons=[],
        improvements=["Демо: снизьте долговую нагрузку"],
    )
    assert DecisionSerializer(officer).data["approval_plan"] is None
