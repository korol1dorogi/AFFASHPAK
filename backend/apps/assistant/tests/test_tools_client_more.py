"""AI18: what_if, approval_plan, explain_check_status, company_metrics, required_documents,
explain_term — the client's own data, the same services as the screens, foreign → not found."""

from decimal import Decimal

import pytest
from rest_framework.test import APIClient

from apps.accounts.demo import seed
from apps.applications.models import BkiConsent, Check
from apps.assistant.tools import TOOLS, run_tool
from apps.business.models import Membership
from apps.core.factories import make_application, make_bank_user
from apps.credit_math import annuity_payment
from apps.integrations.flags import reset
from apps.recommendations.api import what_if_for_user

from .personas import persona_application

pytestmark = pytest.mark.django_db

NEW_TOOLS = (
    "what_if",
    "approval_plan",
    "explain_check_status",
    "company_metrics",
    "required_documents",
    "explain_term",
)


def user_of(username: str):
    return Membership.objects.select_related("user").get(user__username=username).user


@pytest.fixture
def seeded(db):
    seed()
    yield
    reset()


# ───────────────────────── what_if (XP1) ─────────────────────────


def test_what_if_is_the_service_of_the_slider(seeded):
    application = persona_application(3)  # DSCR counteroffer 2 009 314 ₽ at 24 %
    garden = user_of("demo_garden_store")
    arguments = {"application_id": application.pk, "amount": "1500000.00", "term_months": 18}

    result = run_tool(garden, "what_if", arguments)

    assert "error" not in result, result
    direct = what_if_for_user(garden, application.pk, {"amount": "1500000.00", "term_months": 18})
    assert {k: result[k] for k in direct} == direct  # one service, one answer
    expected = annuity_payment(Decimal("1500000.00"), Decimal(result["rate"]), 18)
    assert Decimal(result["monthly_payment"]) == expected
    assert result["note"] == "Это предварительная оценка, а не решение банка."


def test_what_if_refuses_like_the_api(seeded):
    coffee = user_of("demo_coffee_shop")
    draft = make_application(Membership.objects.get(user=coffee).company)
    no_offer = run_tool(
        coffee, "what_if", {"application_id": draft.pk, "amount": "500000.00", "term_months": 6}
    )
    assert no_offer["error"]["code"] not in ("invalid", "unknown_tool")  # 409 of the service

    application = persona_application(3)
    garden = user_of("demo_garden_store")
    out_of_range = run_tool(
        garden, "what_if", {"application_id": application.pk, "amount": "1000000.00",
                            "term_months": 99}
    )  # fmt: skip
    assert out_of_range["error"]["code"] == "invalid"
    assert "term_months" in out_of_range["error"]["details"]


# ───────────────────────── approval_plan (XP2) ─────────────────────────


def test_approval_plan_after_a_decline_by_grade(seeded):
    application = persona_application(5)  # grade E, 47 points
    result = run_tool(user_of("demo_dependent_supplier"), "approval_plan", {})

    assert result["application_id"] == application.pk
    assert result["outcome"] == "declined"
    assert result["grade"] == "E"
    assert result["plan"]["target_grade"] == "C"
    assert result["plan"]["steps"]
    assert result["improvements"]


def test_approval_plan_explains_when_there_is_none(seeded):
    persona_application(1)  # an offer: nothing to plan
    result = run_tool(user_of("demo_coffee_shop"), "approval_plan", {})
    assert result["plan"] is None
    assert "только после автоматического отказа по грейду" in result["message"]


# ───────────────────────── explain_check_status (SRC2) ─────────────────────────


def test_check_statuses_in_plain_words_without_bank_internals(seeded):
    application = persona_application(1)
    result = run_tool(user_of("demo_coffee_shop"), "explain_check_status", {})

    assert result["application_id"] == application.pk
    assert {check["source"] for check in result["checks"]} == {
        "egrul", "transparent_business", "bki", "bank_account",
    }  # fmt: skip
    for check in result["checks"]:
        assert set(check) == {"source", "source_name", "status", "meaning", "what_to_do"}


def test_no_consent_is_explained_as_not_a_decline(seeded):
    application = persona_application(1, run=False)
    BkiConsent.objects.filter(application=application).delete()
    from apps.pipeline.runner import execute

    execute(application.pk)
    result = run_tool(user_of("demo_coffee_shop"), "explain_check_status", {})
    bki = next(check for check in result["checks"] if check["source"] == "bki")
    assert bki["status"] == "consent_missing"
    assert "нет согласия" in bki["meaning"]
    assert "это не отказ" in result["note"]
    assert "проверит сотрудник банка" in bki["what_to_do"]


def test_a_draft_has_no_checks_yet(seeded):
    coffee = user_of("demo_coffee_shop")
    make_application(Membership.objects.get(user=coffee).company)
    result = run_tool(coffee, "explain_check_status", {})
    assert result["checks"] == []
    assert "после отправки" in result["message"]
    assert not Check.objects.exists()


# ───────────────────────── company_metrics ─────────────────────────


def test_company_metrics_are_the_screen_metrics(seeded):
    coffee = user_of("demo_coffee_shop")
    result = run_tool(coffee, "company_metrics", {})

    client = APIClient()
    client.force_login(coffee)
    screen = client.get("/api/company/metrics").json()
    assert result["metrics"] == screen["metrics"]
    assert result["snapshot"] == screen["snapshot"]
    assert run_tool(coffee, "company_metrics", {"inn": "1"})["error"]["code"] == "invalid"


# ───────────────────────── required_documents ─────────────────────────


def test_documents_of_a_product(seeded):
    result = run_tool(
        user_of("demo_coffee_shop"), "required_documents", {"product_code": "investment_loan_basic"}
    )
    assert [doc["kind"] for doc in result["required"]] == [
        "bank_statement", "tax_return", "contract", "invoice",
    ]  # fmt: skip
    assert result["required"][0]["name"] == "Выписка"
    unknown = run_tool(user_of("demo_coffee_shop"), "required_documents", {"product_code": "x"})
    assert unknown["error"]["code"] == "invalid"


def test_documents_of_an_application_with_gaps_and_a_bank_request(seeded):
    application = persona_application(4, run=False)
    application.documents.filter(kind="invoice").delete()
    furniture = user_of("demo_furniture_maker")
    application.info_requests.create(
        origin="officer", message="Нужен договор поставки", document_kinds=["contract", "other"]
    )

    result = run_tool(furniture, "required_documents", {"application_id": application.pk})

    assert [doc["kind"] for doc in result["missing"]] == ["invoice", "other"]
    assert [doc["kind"] for doc in result["requested_by_bank"]] == ["contract", "other"]
    assert "contract" in [doc["kind"] for doc in result["uploaded"]]


# ───────────────────────── explain_term ─────────────────────────


@pytest.mark.parametrize(
    ("asked", "term"),
    [
        ("DSCR", "dscr"),
        ("  Овердрафт ", "овердрафт"),
        ("контроффер", "контрпредложение"),
        ("Debt / EBITDA", "долг/ebitda"),
        ("платеж", "аннуитетный платёж"),
    ],
)
def test_terms_and_their_other_names(seeded, asked, term):
    result = run_tool(user_of("demo_coffee_shop"), "explain_term", {"term": asked})
    assert result["term"] == term
    assert result["explanation"]


def test_an_unknown_term_lists_what_is_known(seeded):
    result = run_tool(user_of("demo_coffee_shop"), "explain_term", {"term": "своп"})
    assert result["error"]["code"] == "not_found"
    assert "овердрафт" in result["error"]["message"]


# ───────────────────────── access ─────────────────────────


@pytest.mark.parametrize("name", NEW_TOOLS)
def test_new_tools_are_not_for_the_bank(seeded, name):
    arguments = {"term": "DSCR"} if name == "explain_term" else {}
    if name == "what_if":
        arguments = {"amount": "100000.00", "term_months": 12}
    result = run_tool(make_bank_user("bank_more"), name, arguments)
    assert result["error"]["code"] == "not_found"


@pytest.mark.parametrize("name", ("what_if", "approval_plan", "explain_check_status",
                                  "required_documents"))  # fmt: skip
def test_a_foreign_application_is_not_found(seeded, name):
    foreign = persona_application(5)
    arguments = {"application_id": foreign.pk}
    if name == "what_if":
        arguments |= {"amount": "100000.00", "term_months": 12}
    result = run_tool(user_of("demo_coffee_shop"), name, arguments)
    assert result["error"]["code"] == "not_found"


def test_every_new_tool_is_registered_and_strict():
    for name in NEW_TOOLS:
        assert name in TOOLS
        assert TOOLS[name].spec.parameters["additionalProperties"] is False


def test_every_client_result_is_plain_json(seeded):
    """The journal (AssistantMessage.tool_calls) stores results as JSON: no Decimal or datetime."""
    import json

    application = persona_application(3)
    garden = user_of("demo_garden_store")
    calls = {
        "recommend_products": {"need_type": "working_capital"},
        "calc_payment": {"principal": "1000000", "annual_rate": "0.24", "term_months": 12},
        "explain_status": {},
        "explain_decision": {},
        "what_if": {"amount": "1500000.00", "term_months": 12},
        "approval_plan": {},
        "explain_check_status": {},
        "company_metrics": {},
        "required_documents": {"application_id": application.pk},
        "explain_term": {"term": "грейд"},
        "create_draft": {
            "need_type": "working_capital",
            "purpose": "Закупка рассады к сезону (демо)",
            "requested_amount": "1000000.00",
            "term_months": 12,
        },
    }
    assert set(calls) == set(TOOLS)
    for name, arguments in calls.items():
        result = run_tool(garden, name, arguments)
        assert "error" not in result, (name, result)
        json.dumps(result)
