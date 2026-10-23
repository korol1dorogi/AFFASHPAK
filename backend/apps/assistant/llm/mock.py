"""Deterministic provider: no network, no key. Default locally, in tests, CI and a clean clone
(LLM_PROVIDER=mock), and the engine's fallback when a live provider fails (AI2).

It plays both profiles — the set of tools tells which: the bank set has `application_summary`.
A user message → keywords pick a tool (the arguments come from the text and the application
number in the <context> block); a tool result → a short answer built only from the results of
this turn, so the numbers in the answer are the tools' numbers. Unclear → one clarifying
question. The scenario-driven mock (AI20) replaces the keyword rules, not this interface.
"""

import json
import re
from decimal import Decimal, InvalidOperation

from apps.assistant.llm.base import LLMResponse, Message, ToolCall, ToolSpec
from apps.assistant.summary import PREFIX as SUMMARY_PREFIX
from apps.assistant.summary import from_facts

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

BANK_CLARIFY = (
    "Могу собрать сводку по заявке, разобрать скоринг, проверки и источники, платёжеспособность, "
    "соответствие политике, что запросить у клиента, или подготовить черновик комментария."
)
BANK_NO_APPLICATION = "Откройте заявку — я работаю с данными конкретной заявки."
BANK_REFUSE = (
    "Решение по заявке и её статус меняет сотрудник в карточке — я только собираю факты "
    "и готовлю черновик комментария."
)
BANK_DECISION_WORDS = ("одобри", "отклони", "откажи", "измени статус", "смени статус", "игнорируй")

_APPLICATION_NUMBER = re.compile(r"Заявка №\s*(\d+)")


def detect_need_type(text: str) -> str | None:
    lowered = text.lower()
    for need_type, keywords in NEED_KEYWORDS:
        if any(word in lowered for word in keywords):
            return need_type
    return None


def _numbers(text: str) -> list[str]:
    return [n.replace(" ", "").replace(",", ".") for n in re.findall(r"\d[\d ]*(?:[.,]\d+)?", text)]


def percent_to_fraction(rate_percent: str) -> str:
    """'24' → '0.24': people speak percent, the API wants an annual fraction."""
    try:
        return str(Decimal(rate_percent) / 100)
    except InvalidOperation:
        return "0"


def _rub(value) -> str:
    """«2009314.00» → «2 009 314 ₽» — the tool's own number, only regrouped."""
    if value in (None, ""):
        return "—"
    amount = Decimal(str(value)).quantize(Decimal("0.01"))
    whole, _, cents = f"{amount:.2f}".partition(".")
    grouped = f"{int(whole):,}".replace(",", " ")
    return f"{grouped},{cents} ₽" if cents != "00" else f"{grouped} ₽"


def _percent(fraction) -> str:
    value = (Decimal(str(fraction)) * 100).normalize()
    return f"{value:f}".replace(".", ",") + " %"


class MockLLMClient:
    def __init__(self) -> None:
        self._counter = 0

    def _call(self, name: str, arguments: dict) -> ToolCall:
        self._counter += 1
        return ToolCall(id=f"call_mock_{self._counter}", name=name, arguments=arguments)

    def complete(self, messages: list[Message], tools: list[ToolSpec]) -> LLMResponse:
        if not messages:
            return LLMResponse(content=CLARIFY)
        available = {tool.name for tool in tools}
        # The bank set has application_summary; the decision summary comes with no tools at all
        # (the engine already read the facts), so its prefix tells the profile too.
        bank = "application_summary" in available or _last_user_text(messages).startswith(
            SUMMARY_PREFIX
        )
        context = messages[0].content if messages[0].role == "system" else ""
        found = _APPLICATION_NUMBER.search(context)
        application_id = int(found.group(1)) if found else None
        last = messages[-1]
        if last.role == "tool":
            results = _turn_results(messages)
            question = _last_user_text(messages)
            return LLMResponse(content=_bank_answer(results, question) if bank else
                               _client_answer(results))  # fmt: skip
        if bank:
            return self._bank_step(last.content, available, application_id)
        return self._client_step(last.content, available, application_id)

    # ───────────────────────── client ─────────────────────────

    def _client_step(self, text: str, available: set[str], application_id: int | None):
        lowered = text.lower()
        ref = {"application_id": application_id} if application_id else {}

        def call(name: str, arguments: dict) -> LLMResponse | None:
            if name not in available:
                return None
            return LLMResponse(content="", tool_calls=(self._call(name, arguments),))

        if any(word in lowered for word in DECISION_WORDS):
            return LLMResponse(content=REFUSE_DECISION)
        if any(word in lowered for word in CALC_KEYWORDS) and CALCULATOR_TOOL in available:
            numbers = _numbers(text)
            if len(numbers) >= 3:
                principal, rate_percent, months = numbers[:3]
                return call(
                    CALCULATOR_TOOL,
                    {
                        "principal": principal,
                        "annual_rate": percent_to_fraction(rate_percent),
                        "term_months": int(months.split(".")[0]),
                    },
                )
            return LLMResponse(
                content="Назовите сумму, ставку в процентах годовых и срок в месяцах."
            )
        if re.search(r"(что|а) если", lowered):
            numbers = [n for n in _numbers(text) if n]
            term = re.search(r"(\d+)\s*(мес|month)", lowered)
            amounts = [n for n in numbers if Decimal(n) >= 10_000]
            if term and amounts:
                return call(
                    "what_if",
                    {**ref, "amount": amounts[0], "term_months": int(term.group(1))},
                ) or LLMResponse(content=CLARIFY)
            if term:
                return LLMResponse(content="Назовите сумму, которую хотите взять на этот срок.")
        if "статус" in lowered or re.search(r"что с (моей |нашей )?заявк", lowered):
            return call("explain_status", ref) or LLMResponse(content=CLARIFY)
        if "почему" in lowered and re.search(r"отказ|меньше|решени|услови", lowered):
            return call("explain_decision", ref) or LLMResponse(content=CLARIFY)
        if "одобрени" in lowered or "что улучшить" in lowered:
            return call("approval_plan", ref) or LLMResponse(content=CLARIFY)
        if "документ" in lowered:
            return call("required_documents", ref) or LLMResponse(content=CLARIFY)
        if re.search(r"проверк|источник", lowered):
            return call("explain_check_status", ref) or LLMResponse(content=CLARIFY)
        if re.search(r"показател|метрик|мои обороты", lowered):
            return call("company_metrics", {}) or LLMResponse(content=CLARIFY)
        term = re.search(r"что (такое|значит|означает)\s+(.+)", text, re.IGNORECASE)
        if term:
            asked = term.group(2).strip(' ?!.«»"')
            return call("explain_term", {"term": asked}) or LLMResponse(content=CLARIFY)
        need_type = detect_need_type(text)
        if need_type and RECOMMEND_TOOL in available:
            return call(RECOMMEND_TOOL, {"need_type": need_type})
        return LLMResponse(content=CLARIFY)

    # ───────────────────────── bank ─────────────────────────

    def _bank_step(self, text: str, available: set[str], application_id: int | None):
        lowered = text.lower()
        if application_id is None:
            return LLMResponse(content=BANK_NO_APPLICATION)
        ref = {"application_id": application_id}

        def calls(*names: str, **extra) -> LLMResponse:
            picked = [self._call(name, {**ref, **extra}) for name in names if name in available]
            return (
                LLMResponse(content="", tool_calls=tuple(picked))
                if picked
                else LLMResponse(content=BANK_CLARIFY)
            )

        if text.startswith(SUMMARY_PREFIX):
            return calls(
                "application_summary", "score_breakdown", "checks_with_provenance",
                "missing_documents",
            )  # fmt: skip
        if "комментари" in lowered:
            intent = "request_info"
            if "отказ" in lowered:
                intent = "decline"
            elif "иные услови" in lowered or "контр" in lowered:
                intent = "counteroffer"
            elif "одобрен" in lowered:
                intent = "approve"
            return calls("draft_officer_comment", preliminary_intent=intent)
        if any(word in lowered for word in BANK_DECISION_WORDS):
            return LLMResponse(content=BANK_REFUSE)
        if re.search(r"грейд|фактор|скоринг|балл", lowered):
            return calls("score_breakdown")
        if "политик" in lowered:
            return calls("policy_compare")
        if re.search(r"dscr|платёжеспособ|платежеспособ|лимит|денежн", lowered):
            return calls("dscr_and_limits")
        if re.search(r"запрос|документ|не хватает", lowered):
            return calls("missing_documents")
        if re.search(r"проверк|источник|бки|егрюл|выписк", lowered):
            return calls("checks_with_provenance")
        if re.search(r"сводк|картин|по заявке|что по|риск", lowered):
            return calls("application_summary", "score_breakdown")
        return LLMResponse(content=BANK_CLARIFY)


# ───────────────────────── answers from this turn's results ─────────────────────────


def _last_user_text(messages: list[Message]) -> str:
    return next((m.content for m in reversed(messages) if m.role == "user"), "")


def _turn_results(messages: list[Message]) -> dict[str, dict]:
    """Results of the tools called after the last user message, by tool name."""
    start = max((i for i, m in enumerate(messages) if m.role == "user"), default=0)
    names: dict[str, str] = {}
    results: dict[str, dict] = {}
    for message in messages[start:]:
        for call in message.tool_calls:
            names[call.id] = call.name
        if message.role == "tool":
            try:
                data = json.loads(message.content)
            except json.JSONDecodeError:
                continue
            name = names.get(message.tool_call_id or "") or _guess_name(data)
            if isinstance(data, dict):
                results[name] = data
    return results


def _guess_name(data) -> str:
    if isinstance(data, dict) and "offers" in data:
        return RECOMMEND_TOOL
    if isinstance(data, dict) and "payment" in data:
        return CALCULATOR_TOOL
    return "unknown"


def _client_answer(results: dict[str, dict]) -> str:
    parts: list[str] = []
    for name, data in results.items():
        if "error" in data:
            parts.append(f"Не получилось: {data['error'].get('message', 'ошибка')}")
            continue
        parts.append(_client_line(name, data))
    return " ".join(part for part in parts if part) or "Готово. Посмотрите результат ниже."


def _client_line(name: str, data: dict) -> str:
    if name == RECOMMEND_TOOL:
        offers = data.get("offers") or []
        if not offers:
            return "Подходящих предложений по данным счёта не нашлось. Это предварительная оценка."
        best = offers[0]
        product = (best.get("product") or {}).get("name", "продукт")
        amount = f" — {product} на {_rub(best['amount'])}" if best.get("amount") else ""
        return (
            f"Подобрал предложений: {len(offers)}{amount}. "
            "Это предварительная оценка, причины — ниже."
        )
    if name == CALCULATOR_TOOL:
        return (
            f"Ежемесячный платёж — {_rub(data['payment'])}, переплата за весь срок — "
            f"{_rub(data.get('overpayment'))} (расчёт калькулятора)."
        )
    if name == "explain_status":
        return f"{data['status_label']}: {data['meaning']} {data['next_step']}"
    if name == "explain_decision":
        decision = data.get("decision")
        if decision is None:
            return data.get("message", "Решения пока нет.")
        failed = [r["message"] for r in decision.get("reasons", []) if r.get("passed") is False]
        why = f" Главное: {failed[0]}." if failed else ""
        return f"Решение: {decision['outcome_text']}.{why} {data.get('note', '')}".strip()
    if name == "create_draft":
        pending = data.get("pending_action") or {}
        return f"{pending.get('summary', '')} Чтобы создать черновик, нажмите «Подтвердить»."
    if name == "what_if":
        verdict = "проходит" if data.get("fits") else "не проходит"
        return (
            f"При {_rub(data['amount'])} на {data['term_months']} мес платёж — "
            f"{_rub(data['monthly_payment'])}, по денежному потоку {verdict}. "
            "Это предварительная оценка."
        )
    if name == "approval_plan":
        plan = data.get("plan")
        if not plan:
            return data.get("message", "Плана пока нет.")
        steps = "; ".join(step["message"] for step in plan.get("steps", [])[:3])
        return f"Чтобы выйти на грейд {plan['target_grade']}: {steps}. Это предварительная оценка."
    if name == "explain_check_status":
        lines = [f"{c['source_name']} — {c['meaning']}" for c in data.get("checks", [])]
        return "; ".join(lines) + "." if lines else data.get("message", "")
    if name == "company_metrics":
        metrics = [m["message"] for m in data.get("metrics", [])[:3]]
        return "; ".join(metrics) + "." if metrics else data.get("message", "")
    if name == "required_documents":
        missing = data.get("missing")
        if missing is not None:
            names = ", ".join(d["name"] for d in missing)
            return f"Не хватает: {names}." if names else "Все нужные документы загружены."
        return "Нужны: " + ", ".join(d["name"] for d in data.get("required", [])) + "."
    if name == "explain_term":
        return data["explanation"]
    return "Готово. Посмотрите результат ниже."


def _bank_answer(results: dict[str, dict], question: str) -> str:
    if question.startswith(SUMMARY_PREFIX):
        clean = {name: data for name, data in results.items() if "error" not in data}
        return json.dumps(from_facts(clean), ensure_ascii=False)
    parts: list[str] = []
    for name, data in results.items():
        if "error" in data:
            parts.append(f"Не получилось: {data['error'].get('message', 'ошибка')}")
            continue
        parts.append(_bank_line(name, data))
    return " ".join(part for part in parts if part) or BANK_CLARIFY


def _bank_line(name: str, data: dict) -> str:
    if name == "application_summary":
        decision = data.get("decision") or {}
        grade = f", грейд {decision['grade']}" if decision.get("grade") else ""
        product = (data.get("product") or {}).get("name", "продукт не выбран")
        return (
            f"Заявка №{data['application_id']}: {data['status_label']}{grade}; "
            f"{product}, {_rub(data['requested_amount'])} на {data['term_months']} мес."
        )
    if name == "score_breakdown":
        if data.get("score", True) is None:
            return data.get("message", "")
        losing = [f["message"] for f in data.get("factors", []) if f.get("lost_points")][:2]
        tail = f" Больше всего баллов теряют: {'; '.join(losing)}." if losing else ""
        return f"Грейд {data['grade']} ({data['total']} из 100).{tail}"
    if name == "checks_with_provenance":
        lines = [f"{c['source_name']} — {c['meaning']}" for c in data.get("checks", [])]
        return "; ".join(lines) + "." if lines else data.get("message", "")
    if name == "dscr_and_limits":
        lines = [item["message"] for item in data.get("limits", [])]
        if data.get("message"):
            lines.insert(0, data["message"])
        return "; ".join(lines) + "." if lines else "Лимиты по заявке не посчитаны."
    if name == "policy_compare":
        stops = [s["code"] for s in data.get("stop_factors", [])]
        failed = [row["message"] for row in data.get("rows", []) if row.get("passed") is False]
        if stops:
            return "Стоп-фактор: " + "; ".join(stops) + "."
        if failed:
            return "Не проходит по политике: " + "; ".join(failed[:3]) + "."
        return "По требованиям продукта и порогам политики заявка проходит."
    if name == "missing_documents":
        items = [d["name"] for d in data.get("missing_product_documents", [])]
        items += [item["ask"] for item in data.get("because_of_sources", [])]
        items += [gap["message"] for gap in data.get("field_gaps", [])]
        return (
            ("Запросить у клиента: " + "; ".join(items) + ".")
            if items
            else ("Всё нужное для решения есть.")
        )
    if name == "draft_officer_comment":
        warnings = " ".join(data.get("warnings", []))
        return f"Черновик комментария: {data['draft_comment']} {warnings}".strip()
    return BANK_CLARIFY
