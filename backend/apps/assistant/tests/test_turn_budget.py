"""A slow model ends in the mock's answer, not in a killed request (the 500 on the stand, 24.10);
cars are capex for the mock; the clarifying question is not repeated word for word."""

import pytest

from apps.accounts.demo import seed
from apps.assistant import engine
from apps.assistant.llm import LLMResponse, ToolCall
from apps.assistant.llm.base import Message
from apps.assistant.llm.mock import (
    CLARIFY,
    CLARIFY_AGAIN,
    PERSONAL,
    REFUSE_PERSONAL,
    MockLLMClient,
    detect_need_type,
)
from apps.business.models import Membership
from apps.integrations.flags import reset


class Scripted:
    def __init__(self, *responses):
        self.responses = list(responses)
        self.sent: list = []

    def complete(self, messages, tools):
        self.sent.append([*messages])
        return self.responses.pop(0)


@pytest.fixture
def coffee(db, settings):
    settings.LLM_PROVIDER = "mock"
    seed()
    yield Membership.objects.select_related("user").get(user__username="demo_coffee_shop").user
    reset()


def test_an_exhausted_budget_hands_the_turn_to_the_mock(coffee, monkeypatch, settings):
    settings.LLM_TURN_BUDGET_SECONDS = 0
    client = Scripted(LLMResponse("никогда не прозвучит"))
    monkeypatch.setattr(engine, "get_llm_client", lambda: client)
    answer = engine.respond(coffee, "client", "Что такое овердрафт?")
    assert client.sent == []  # no request started past the budget
    assert answer.fallback is True
    assert answer.reply.startswith(engine.UNAVAILABLE)
    assert "Лимит на расчётном счёте" in answer.reply  # the mock finished the turn


def test_the_budget_stops_between_steps_and_keeps_the_results(coffee, monkeypatch, settings):
    settings.LLM_TURN_BUDGET_SECONDS = 30
    call = ToolCall(
        "c1", "calc_payment", {"principal": "1000000", "annual_rate": "0.24", "term_months": 12}
    )
    client = Scripted(LLMResponse("", (call,)), LLMResponse("второй шаг не начнётся"))
    # the first model request «takes» 100 s: the clock jumps once it has been made
    monkeypatch.setattr(engine.time, "monotonic", lambda: 100.0 if client.sent else 0.0)
    monkeypatch.setattr(engine, "get_llm_client", lambda: client)
    answer = engine.respond(coffee, "client", "Сколько платить?")
    assert len(client.sent) == 1
    assert answer.fallback is True
    assert "94 559,60 ₽" in answer.reply  # the calculator's result, not lost


def test_the_mock_is_never_limited_by_the_budget(coffee, settings):
    settings.LLM_TURN_BUDGET_SECONDS = 0
    answer = engine.respond(coffee, "client", "Что такое овердрафт?")
    assert answer.fallback is False
    assert "Лимит на расчётном счёте" in answer.reply


@pytest.mark.parametrize(
    "text",
    [
        "нужен кредит на машину",
        "на автомобиль",
        "купить грузовик",
        "фургон для доставки",
        "деньги на авто для курьеров",
        "спецтехника",
    ],
)
def test_cars_are_capex(text):
    assert detect_need_type(text) == "capex"


def test_automatic_is_not_a_car():
    assert detect_need_type("автоматически списывать") is None


def test_cash_is_not_personal():
    assert PERSONAL.search("машина для себя")
    assert not PERSONAL.search("не хватает наличных на зарплату")


def _ask(*history: tuple[str, str]) -> str:
    messages = [Message(role="system", content="контекст")]
    messages += [Message(role=role, content=text) for role, text in history]
    return MockLLMClient().complete(messages, []).content


def test_the_clarifying_question_is_not_repeated():
    assert _ask(("user", "нужен кредит")) == CLARIFY
    again = _ask(("user", "нужен кредит"), ("assistant", CLARIFY), ("user", "ну деньги"))
    assert again == CLARIFY_AGAIN


def test_a_personal_car_is_refused_with_the_business_option():
    assert _ask(("user", "кредит на машину для себя")) == REFUSE_PERSONAL
