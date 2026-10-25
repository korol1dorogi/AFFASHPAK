"""AI1: assistant tools act as the current user, see only their company and never act alone."""

import uuid
from datetime import timedelta
from decimal import Decimal

import pytest
from django.utils import timezone
from rest_framework.exceptions import NotFound

from apps.accounts.demo import seed
from apps.applications.models import Application
from apps.assistant.models import PendingAction
from apps.assistant.tools import (
    TOOLS,
    confirm_pending_action,
    run_tool,
    tool_specs,
)
from apps.business.models import Membership
from apps.core.factories import make_application, make_bank_user
from apps.integrations.flags import reset
from apps.pipeline.runner import execute
from apps.pipeline.tests.test_personas import _application, _documents

pytestmark = pytest.mark.django_db

DRAFT = {
    "need_type": "cash_gap",
    "purpose": "Зарплата до поступления оплаты от покупателей",
    "requested_amount": "900000.00",
    "term_months": 12,
    "product_code": "overdraft_basic",
}


@pytest.fixture
def people(db):
    seed()
    coffee = Membership.objects.select_related("user", "company").get(
        user__username="demo_coffee_shop"
    )
    other = Membership.objects.select_related("user", "company").get(
        user__username="demo_retail_supplier"
    )
    yield {
        "coffee": coffee.user,
        "coffee_company": coffee.company,
        "other": other.user,
        "other_company": other.company,
        "bank": make_bank_user("bank_tools"),
    }
    reset()


def test_the_tool_list_matches_the_task():
    assert set(TOOLS) == {
        "recommend_products",
        "calc_payment",
        "explain_status",
        "explain_decision",
        "create_draft",
        # AI18
        "what_if",
        "approval_plan",
        "explain_check_status",
        "company_metrics",
        "required_documents",
        "explain_term",
    }
    for spec in tool_specs():
        assert spec.description
        assert spec.parameters["type"] == "object"
        assert spec.parameters["additionalProperties"] is False


# ───────────────────────── recommend_products ─────────────────────────


def test_recommend_products_uses_the_users_company(people):
    result = run_tool(people["coffee"], "recommend_products", {"need_type": "cash_gap"})
    assert "error" not in result
    assert result["is_preliminary"] is True
    assert result["note"] == "Это предварительная оценка, а не решение банка."
    first = result["offers"][0]
    assert first["product"]["kind"] == "overdraft"
    assert first["amount"] == "900000.00"  # persona 1: limit from the coffee shop's turnover
    assert all("message" in reason for reason in first["reasons"])


def test_recommend_products_validates_like_the_api(people):
    result = run_tool(people["coffee"], "recommend_products", {"need_type": "receivable_delay"})
    assert result["error"]["code"] == "invalid"
    assert "invoice_amount" in result["error"]["details"]
    arguments = {"need_type": "cash_gap", "rate": "0"}
    sneaky = run_tool(people["coffee"], "recommend_products", arguments)
    assert sneaky["error"]["code"] == "invalid"


def test_recommend_products_is_not_for_the_bank(people):
    result = run_tool(people["bank"], "recommend_products", {"need_type": "cash_gap"})
    assert result["error"]["code"] == "not_found"


# ───────────────────────── calc_payment ─────────────────────────


def test_calc_payment_comes_from_credit_math(people):
    result = run_tool(
        people["coffee"],
        "calc_payment",
        {"principal": "1000000", "annual_rate": "0.24", "term_months": 12},
    )
    assert result["payment"] == "94559.60"
    assert Decimal(result["total_paid"]) - Decimal("1000000.00") == Decimal(result["overpayment"])


def test_calc_payment_rejects_bad_input(people):
    arguments = {"principal": "-5", "annual_rate": "0.2", "term_months": 0}
    result = run_tool(people["coffee"], "calc_payment", arguments)
    assert result["error"]["code"] == "invalid"
    assert {"principal", "term_months"} <= set(result["error"]["details"])


def test_calc_payment_refuses_a_rate_in_percent(people):
    """A live model sent «24» for 24 %: an error the model can fix, never a 2400 % payment."""
    arguments = {"principal": "1000000", "annual_rate": "24", "term_months": 12}
    result = run_tool(people["coffee"], "calc_payment", arguments)
    assert result["error"]["code"] == "invalid"
    assert "0.24" in result["error"]["details"]["annual_rate"][0]


# ───────────────────────── explain_status ─────────────────────────


def test_explain_status_speaks_plainly_and_lists_actions(people):
    application = make_application(people["coffee_company"])
    result = run_tool(people["coffee"], "explain_status", {"application_id": application.pk})
    assert result["status"] == "draft"
    assert result["status_label"] == "Черновик"
    assert result["next_step"].startswith("Проверьте данные")
    assert "submit" in result["available_actions"]  # the coffee shop's director is a signatory


def test_explain_status_defaults_to_the_latest_application(people):
    make_application(people["coffee_company"])
    latest = make_application(people["coffee_company"], status="manual_review")
    result = run_tool(people["coffee"], "explain_status", {})
    assert result["application_id"] == latest.pk
    assert result["status_label"] == "У сотрудника банка"


def test_explain_status_of_a_foreign_application_is_not_found(people):
    foreign = make_application(people["other_company"])
    result = run_tool(people["coffee"], "explain_status", {"application_id": foreign.pk})
    assert result == {"error": {"code": "not_found", "message": "Не найдено."}}


def test_explain_status_never_takes_the_latest_application_of_someone_else(people):
    make_application(people["other_company"])
    result = run_tool(people["coffee"], "explain_status", {})
    assert result["error"]["code"] == "not_found"


# ───────────────────────── explain_decision ─────────────────────────


def test_explain_decision_gives_reasons_and_the_offer(people):
    application = _application("demo_coffee_shop", "overdraft_basic", "900000.00", 12)
    _documents(application, tuple(application.product.required_documents))
    execute(application.pk)

    result = run_tool(people["coffee"], "explain_decision", {"application_id": application.pk})

    decision = result["decision"]
    assert decision["outcome"] == "offer"
    assert decision["is_preliminary"] is True
    assert decision["reasons"]
    assert result["note"] == "Это предварительная оценка, а не решение банка."
    assert result["offer"]["amount"] == "900000.00"
    assert result["offer"]["product"]


def test_explain_decision_without_a_decision(people):
    application = make_application(people["coffee_company"])
    result = run_tool(people["coffee"], "explain_decision", {"application_id": application.pk})
    assert result["decision"] is None
    assert result["message"] == "Решения по заявке пока нет."


def test_explain_decision_of_a_foreign_application_is_not_found(people):
    foreign = make_application(people["other_company"], status="declined")
    result = run_tool(people["coffee"], "explain_decision", {"application_id": foreign.pk})
    assert result["error"]["code"] == "not_found"


# ───────────────────────── create_draft ─────────────────────────


def test_create_draft_only_proposes_an_action(people):
    before = Application.objects.count()

    result = run_tool(people["coffee"], "create_draft", DRAFT)

    assert Application.objects.count() == before  # nothing until the human confirms
    pending = result["pending_action"]
    assert pending["kind"] == "create_application"
    assert pending["application_id"] is None
    assert "900 000 ₽" in pending["summary"].replace("\xa0", " ")
    assert "Отправите заявку в банк вы сами" in pending["summary"]
    action = PendingAction.objects.get(pk=pending["id"])
    assert action.user == people["coffee"]
    assert action.status == "pending"
    assert action.payload["prefill_source"] == "assistant"


def test_confirm_creates_the_draft_for_the_users_company_only(people):
    pending = run_tool(people["coffee"], "create_draft", DRAFT)["pending_action"]

    application = confirm_pending_action(people["coffee"], pending["id"])

    assert application.company == people["coffee_company"]
    assert application.created_by == people["coffee"]
    assert application.status == "draft"  # a draft, never submitted by the assistant
    assert application.prefill_source == "assistant"
    assert application.requested_amount == Decimal("900000.00")
    action = PendingAction.objects.get(pk=pending["id"])
    assert action.status == "done"
    assert action.application == application


def test_confirm_twice_is_a_conflict(people):
    pending = run_tool(people["coffee"], "create_draft", DRAFT)["pending_action"]
    confirm_pending_action(people["coffee"], pending["id"])
    with pytest.raises(Exception) as caught:
        confirm_pending_action(people["coffee"], pending["id"])
    assert caught.value.status_code == 409
    assert Application.objects.filter(prefill_source="assistant").count() == 1


def test_an_expired_action_is_a_conflict(people):
    pending = run_tool(people["coffee"], "create_draft", DRAFT)["pending_action"]
    PendingAction.objects.filter(pk=pending["id"]).update(
        expires_at=timezone.now() - timedelta(seconds=1)
    )
    with pytest.raises(Exception) as caught:
        confirm_pending_action(people["coffee"], pending["id"])
    assert caught.value.status_code == 409


def test_someone_elses_action_is_not_found(people):
    pending = run_tool(people["coffee"], "create_draft", DRAFT)["pending_action"]
    with pytest.raises(NotFound):
        confirm_pending_action(people["other"], pending["id"])
    with pytest.raises(NotFound):
        confirm_pending_action(people["coffee"], uuid.uuid4())
    assert not Application.objects.filter(prefill_source="assistant").exists()


def test_create_draft_cannot_set_the_status_or_the_source(people):
    result = run_tool(
        people["coffee"], "create_draft", {**DRAFT, "status": "offer", "approved_amount": "1"}
    )
    assert result["error"]["code"] == "invalid"
    assert {"status", "approved_amount"} <= set(result["error"]["details"])
    assert not PendingAction.objects.exists()


def test_create_draft_validates_like_the_api(people):
    result = run_tool(
        people["coffee"], "create_draft", {**DRAFT, "requested_amount": "0", "product_code": "nope"}
    )
    assert result["error"]["code"] == "invalid"
    assert not PendingAction.objects.exists()


def test_create_draft_is_not_for_the_bank(people):
    result = run_tool(people["bank"], "create_draft", DRAFT)
    assert result["error"]["code"] == "not_found"
    assert not PendingAction.objects.exists()


# ───────────────────────── run_tool ─────────────────────────


@pytest.mark.parametrize(
    ("name", "arguments", "code"),
    [
        ("approve_application", {}, "unknown_tool"),
        ("explain_status", ["not", "an", "object"], "invalid"),
        ("explain_status", {"application_id": "abc"}, "invalid"),
    ],
)
def test_a_bad_call_comes_back_as_data(people, name, arguments, code):
    assert run_tool(people["coffee"], name, arguments)["error"]["code"] == code
