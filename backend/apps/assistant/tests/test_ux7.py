"""UX7: an empty model answer after tools becomes the answer from the results; an assessment
always says it is preliminary; the officer sees factor names, not keys."""

import pytest

from apps.accounts.demo import seed
from apps.assistant import engine, summary
from apps.assistant.llm import LLMResponse, ToolCall
from apps.assistant.tools_bank import FACTOR_LABELS
from apps.business.models import Membership
from apps.integrations.flags import reset


class Scripted:
    def __init__(self, *responses):
        self.responses = list(responses)

    def complete(self, messages, tools):
        return self.responses.pop(0)


@pytest.fixture
def coffee(db, settings):
    settings.LLM_PROVIDER = "mock"
    seed()
    yield Membership.objects.select_related("user").get(user__username="demo_coffee_shop").user
    reset()


CALC = ToolCall(
    "c1", "calc_payment", {"principal": "1000000", "annual_rate": "0.24", "term_months": 12}
)
PICK = ToolCall("p1", "recommend_products", {"need_type": "cash_gap"})


def test_an_empty_answer_after_tools_is_built_from_the_results(coffee, monkeypatch):
    client = Scripted(LLMResponse("", (CALC,)), LLMResponse(""))
    monkeypatch.setattr(engine, "get_llm_client", lambda: client)
    answer = engine.respond(coffee, "client", "Сколько платить?")
    assert "94 559,60 ₽" in answer.reply
    assert engine.UNAVAILABLE_ONLY not in answer.reply
    assert "empty_answer" in answer.guard_triggers


def test_a_pick_always_says_it_is_preliminary(coffee, monkeypatch):
    client = Scripted(LLMResponse("", (PICK,)), LLMResponse("Подходит овердрафт на 900 000 ₽."))
    monkeypatch.setattr(engine, "get_llm_client", lambda: client)
    answer = engine.respond(coffee, "client", "Зарплата 5-го, а клиенты платят 10-го")
    assert answer.reply.endswith(engine.PRELIMINARY_NOTE)


def test_the_note_is_not_doubled_and_not_added_to_a_calculation(coffee, monkeypatch):
    said = "Подходит овердрафт. Это предварительная оценка."
    client = Scripted(LLMResponse("", (PICK,)), LLMResponse(said))
    monkeypatch.setattr(engine, "get_llm_client", lambda: client)
    assert engine.respond(coffee, "client", "Подбери").reply == said
    client = Scripted(LLMResponse("", (CALC,)), LLMResponse("Платёж — 94 559,60 ₽."))
    monkeypatch.setattr(engine, "get_llm_client", lambda: client)
    assert engine.respond(coffee, "client", "Сколько платить?").reply == "Платёж — 94 559,60 ₽."


def test_the_decision_summary_names_factors_as_the_card_does():
    results = {
        "score_breakdown": {
            "grade": "E",
            "total": 47,
            "factors": [
                {
                    "name": "debt_to_ebitda",
                    "label": FACTOR_LABELS["debt_to_ebitda"],
                    "value": "4.2",
                    "passed": False,
                    "message": "Долги — 4,2 годовых прибыли",
                },
            ],
        }
    }
    built = summary.from_facts(results)
    assert built["sources"] == ["скоринг: «Долговая нагрузка (долг к EBITDA)»"]
    assert "debt_to_ebitda" not in str(built)
