"""AI3: the assistant endpoints by the contract — both profiles, access, validation, throttling."""

import uuid

import pytest
from rest_framework.test import APIClient
from rest_framework.throttling import ScopedRateThrottle

from apps.accounts.demo import seed
from apps.applications.models import Application
from apps.assistant.tools import run_tool
from apps.business.models import Membership
from apps.core.factories import make_bank_user
from apps.core.testing import assert_matches_contract
from apps.integrations.flags import reset

from .personas import persona_application

pytestmark = pytest.mark.django_db

MESSAGES = "/api/assistant/messages"


def client_for(user) -> APIClient:
    client = APIClient()
    client.force_login(user)
    return client


def user_of(username: str):
    return Membership.objects.select_related("user").get(user__username=username).user


def bank_url(pk: int, suffix: str) -> str:
    return f"/api/bank/applications/{pk}/assistant/{suffix}"


@pytest.fixture
def world(db, settings):
    settings.LLM_PROVIDER = "mock"
    seed()
    coffee = user_of("demo_coffee_shop")
    bank = make_bank_user("bank_api_ai3")
    yield {
        "coffee": coffee,
        "as_coffee": client_for(coffee),
        "as_supplier": client_for(user_of("demo_dependent_supplier")),
        "bank": bank,
        "as_bank": client_for(bank),
    }
    reset()


# ───────────────────────── client ─────────────────────────


def test_client_message_and_history_match_the_contract(world):
    body = {"text": "Зарплата 5-го, а клиенты платят 10-го"}
    sent = world["as_coffee"].post(MESSAGES, body, format="json")
    assert sent.status_code == 200, sent.content
    assert_matches_contract(sent, method="post", path=MESSAGES, request_body=body)
    assert sent.json()["tool_calls"][0]["name"] == "recommend_products"

    history = world["as_coffee"].get(MESSAGES)
    assert_matches_contract(history, method="get", path=MESSAGES)
    assert [m["role"] for m in history.json()] == ["user", "assistant"]


def test_client_history_is_per_application(world):
    application = persona_application(1)
    body = {"text": "Что с моей заявкой?", "application_id": application.pk}
    world["as_coffee"].post(MESSAGES, body, format="json")
    on_application = world["as_coffee"].get(MESSAGES, {"application_id": application.pk})
    assert len(on_application.json()) == 2
    assert world["as_coffee"].get(MESSAGES).json() == []  # the general chat is separate


def test_someone_elses_application_is_404(world):
    foreign = persona_application(5)
    body = {"text": "Что с заявкой?", "application_id": foreign.pk}
    sent = world["as_coffee"].post(MESSAGES, body, format="json")
    assert sent.status_code == 404
    assert world["as_coffee"].get(MESSAGES, {"application_id": foreign.pk}).status_code == 404


def test_the_client_assistant_is_404_for_the_bank(world):
    assert world["as_bank"].post(MESSAGES, {"text": "привет"}, format="json").status_code == 404
    assert world["as_bank"].get(MESSAGES).status_code == 404


@pytest.mark.parametrize(
    "body",
    [{}, {"text": ""}, {"text": "а" * 2001}, {"text": "ок", "status": "approved"}],
)
def test_bad_message_is_400(world, body):
    response = world["as_coffee"].post(MESSAGES, body, format="json")
    assert response.status_code == 400
    assert_matches_contract(response, method="post", path=MESSAGES, request_body=body)


def test_anonymous_is_401(world):
    assert APIClient().post(MESSAGES, {"text": "привет"}, format="json").status_code == 401


# ───────────────────────── confirm ─────────────────────────


def _pending(user) -> str:
    arguments = {
        "need_type": "cash_gap",
        "purpose": "Зарплата до поступлений (демо)",
        "requested_amount": "900000.00",
        "term_months": 12,
        "product_code": "overdraft_basic",
    }
    return run_tool(user, "create_draft", arguments)["pending_action"]["id"]


def test_confirm_creates_the_draft_by_the_contract(world):
    action_id = _pending(world["coffee"])
    path = f"/api/assistant/actions/{action_id}/confirm"
    response = world["as_coffee"].post(path)
    assert response.status_code == 200, response.content
    assert_matches_contract(response, method="post", path=path)
    body = response.json()
    assert body["status"] == "done"
    assert body["application"]["status"] == "draft"
    assert body["application"]["prefill_source"] == "assistant"

    again = world["as_coffee"].post(path)
    assert again.status_code == 409
    assert_matches_contract(again, method="post", path=path)


def test_confirm_someone_elses_or_unknown_action_is_404(world):
    action_id = _pending(world["coffee"])
    before = Application.objects.count()
    for client, action in ((world["as_supplier"], action_id), (world["as_coffee"], uuid.uuid4())):
        path = f"/api/assistant/actions/{action}/confirm"
        response = client.post(path)
        assert response.status_code == 404
        assert_matches_contract(response, method="post", path=path)
    assert world["as_bank"].post(f"/api/assistant/actions/{action_id}/confirm").status_code == 404
    assert Application.objects.count() == before


# ───────────────────────── bank ─────────────────────────


def test_bank_message_and_history_match_the_contract(world):
    application = persona_application(4)
    path = bank_url(application.pk, "messages")
    body = {"text": "Почему грейд C?"}
    sent = world["as_bank"].post(path, body, format="json")
    assert sent.status_code == 200, sent.content
    assert_matches_contract(sent, method="post", path=path, request_body=body)
    assert sent.json()["pending_action"] is None
    assert sent.json()["tool_calls"][0]["name"] == "score_breakdown"

    history = world["as_bank"].get(path)
    assert_matches_contract(history, method="get", path=path)
    assert len(history.json()) == 2


def test_bank_summary_matches_the_contract_and_changes_nothing(world):
    application = persona_application(5)
    before = (application.status, application.version)
    path = bank_url(application.pk, "summary")
    response = world["as_bank"].post(path)
    assert response.status_code == 200, response.content
    assert_matches_contract(response, method="post", path=path)
    assert response.json()["risks"]
    application.refresh_from_db()
    assert (application.status, application.version) == before


@pytest.mark.parametrize("suffix", ["messages", "summary"])
def test_bank_assistant_is_403_for_clients_and_404_for_unknown(world, suffix):
    application = persona_application(1)
    body = {"text": "сводка"} if suffix == "messages" else None
    own = world["as_coffee"].post(bank_url(application.pk, suffix), body, format="json")
    assert own.status_code == 403
    assert_matches_contract(own, method="post", path=bank_url(application.pk, suffix))
    unknown = world["as_bank"].post(bank_url(999_999, suffix), body, format="json")
    assert unknown.status_code == 404
    assert_matches_contract(unknown, method="post", path=bank_url(999_999, suffix))


def test_bank_message_rejects_an_application_id_in_the_body(world):
    application = persona_application(1)
    body = {"text": "сводка", "application_id": application.pk}
    response = world["as_bank"].post(bank_url(application.pk, "messages"), body, format="json")
    assert response.status_code == 400


# ───────────────────────── throttling ─────────────────────────


def test_flooding_the_model_is_429_but_reading_is_free(world, monkeypatch):
    monkeypatch.setitem(ScopedRateThrottle.THROTTLE_RATES, "assistant", "2/min")
    statuses = [
        world["as_coffee"].post(MESSAGES, {"text": "Что такое грейд?"}, format="json").status_code
        for _ in range(3)
    ]
    assert statuses == [200, 200, 429]
    flooded = world["as_coffee"].post(MESSAGES, {"text": "ещё"}, format="json")
    assert_matches_contract(flooded, method="post", path=MESSAGES, request_body={"text": "ещё"})
    assert world["as_coffee"].get(MESSAGES).status_code == 200  # history is not throttled
