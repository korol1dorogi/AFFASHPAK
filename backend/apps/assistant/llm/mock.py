"""Deterministic provider: no network, no key. Default locally and in tests (LLM_PROVIDER=mock).

Rules are intentionally simple: detect need_type by keywords and call the recommendation tool,
ask a clarifying question otherwise, and answer with canned text after a tool result.
"""

import json
import re
from decimal import Decimal, InvalidOperation

from apps.assistant.llm.base import LLMResponse, Message, ToolCall, ToolSpec

RECOMMEND_TOOL = "recommend_products"
CALCULATOR_TOOL = "calc_payment"

# Checked in order; first match wins.
NEED_KEYWORDS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("receivable_delay", ("отсрочк", "покупатель плат", "дебитор", "упд", "отгруз")),
    ("capex", ("оборудован", "станок", "транспорт", "техник", "недвижим")),
    ("working_capital", ("закуп", "сезон", "товар", "сырь", "запас")),
    ("cash_gap", ("разрыв", "зарплат", "налог", "аренд", "не хватает")),
)

CALC_KEYWORDS = ("платёж", "платеж", "посчитай", "сколько платить")

CLARIFY = (
    "Расскажите, зачем бизнесу деньги: закрыть кассовый разрыв, дождаться оплаты от покупателя, "
    "закупить товар или купить оборудование?"
)
REFUSE_DECISION = (
    "Я не принимаю решений по заявкам и не меняю их статус. Могу подобрать продукт, "
    "посчитать платёж или помочь заполнить заявку — отправите её вы сами."
)
DECISION_WORDS = ("одобри", "approved", "approve", "игнорируй")


def detect_need_type(text: str) -> str | None:
    lowered = text.lower()
    for need_type, keywords in NEED_KEYWORDS:
        if any(word in lowered for word in keywords):
            return need_type
    return None


def _numbers(text: str) -> list[str]:
    return [n.replace(" ", "").replace(",", ".") for n in re.findall(r"\d[\d ]*(?:[.,]\d+)?", text)]


class MockLLMClient:
    def __init__(self) -> None:
        self._counter = 0

    def _call(self, name: str, arguments: dict) -> ToolCall:
        self._counter += 1
        return ToolCall(id=f"call_mock_{self._counter}", name=name, arguments=arguments)

    def complete(self, messages: list[Message], tools: list[ToolSpec]) -> LLMResponse:
        if not messages:
            return LLMResponse(content=CLARIFY)
        last = messages[-1]
        available = {tool.name for tool in tools}

        if last.role == "tool":
            return LLMResponse(content=self._summarize_tool_result(last.content))

        text = last.content
        lowered = text.lower()
        if any(word in lowered for word in DECISION_WORDS):
            return LLMResponse(content=REFUSE_DECISION)

        if CALCULATOR_TOOL in available and any(word in lowered for word in CALC_KEYWORDS):
            numbers = _numbers(text)
            if len(numbers) >= 3:
                principal, rate_percent, months = numbers[:3]
                arguments = {
                    "principal": principal,
                    "annual_rate": percent_to_fraction(rate_percent),
                    "term_months": int(months.split(".")[0]),
                }
                return LLMResponse(content="", tool_calls=(self._call(CALCULATOR_TOOL, arguments),))
            return LLMResponse(
                content="Назовите сумму, ставку в процентах годовых и срок в месяцах."
            )

        need_type = detect_need_type(text)
        if need_type and RECOMMEND_TOOL in available:
            call = self._call(RECOMMEND_TOOL, {"need_type": need_type})
            return LLMResponse(content="", tool_calls=(call,))
        return LLMResponse(content=CLARIFY)

    @staticmethod
    def _summarize_tool_result(content: str) -> str:
        try:
            data = json.loads(content)
        except json.JSONDecodeError:
            return "Готово. Посмотрите результат ниже."
        if isinstance(data, dict) and "offers" in data:
            count = len(data["offers"])
            return f"Подобрал предложений: {count}. Это предварительная оценка, причины — ниже."
        if isinstance(data, dict) and "payment" in data:
            return f"Ежемесячный платёж — {data['payment']} ₽ (расчёт калькулятора)."
        return "Готово. Посмотрите результат ниже."


def percent_to_fraction(rate_percent: str) -> str:
    """'24' → '0.24': people speak percent, the API wants an annual fraction."""
    try:
        return str(Decimal(rate_percent) / 100)
    except InvalidOperation:
        return "0"
