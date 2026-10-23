"""The assistant's orchestrator (AI2, interface И1): one turn of a dialogue for both profiles.

`reply(user, profile, text, application_id)` → a dict in the shape of AssistantReply:
- the profile picks the prompt (И2) and the tool set (И3): the client's tools.py or the bank's
  read-only tools_bank.py — a model of one profile never sees the other's tools;
- the system prompt gets {application_context}: the application in a few lines, cut to ~1500
  characters, with every text a person typed fenced as data (guards.wrap_untrusted, attack 6);
- history — the last 10 messages of this user on this application;
- the model ↔ tools loop runs at most LLM_MAX_STEPS rounds (guards cap the calls per turn);
  every call goes to AssistantMessage.tool_calls and to the log with the correlation id (OPS5);
- a provider that fails or times out does not leave the user without an answer: the turn goes on
  with the deterministic mock and the answer says honestly «ассистент сейчас недоступен».
The assistant never changes an application: the client's changes are PendingActions confirmed by
a human, the bank's tools only read.

`summary(user, application_id)` — «Сводка для решения» (И2а): a «[СВОДКА]» turn whose JSON is
checked; a broken answer is replaced by the summary built from the tools' facts.
"""

import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Literal

from django.conf import settings
from django.contrib.auth.models import AbstractBaseUser
from django.utils import timezone
from rest_framework.exceptions import NotFound, ValidationError

from apps.applications.access import (
    NOT_FOUND,
    client_applications,
    get_client_application,
    is_bank_user,
)
from apps.applications.models import Application
from apps.applications.offers import current_offer
from apps.assistant import guards, prompts, tools, tools_bank
from apps.assistant import summary as summary_module
from apps.assistant.llm import LLMError, Message, MockLLMClient, get_llm_client
from apps.assistant.models import AssistantMessage, MessageRole
from apps.core import context
from apps.scoring.texts import rubles

Profile = Literal["client", "bank"]
logger = logging.getLogger(__name__)

HISTORY = 10
CONTEXT_LIMIT = 1500
UNAVAILABLE = "Ассистент сейчас недоступен, отвечаю в упрощённом режиме."
UNAVAILABLE_ONLY = (
    "Ассистент сейчас недоступен. Подбор, заявка и все расчёты работают в кабинете как обычно."
)
STEPS_EXCEEDED = "Не успел собрать ответ за отведённое число шагов — уточните вопрос, пожалуйста."
SUMMARY_REQUEST = f"{summary_module.PREFIX} Сделай сводку для решения по заявке."
SUMMARY_TOOLS = ("application_summary", "score_breakdown", "checks_with_provenance",
                 "missing_documents")  # fmt: skip
MONTHS = (
    "января", "февраля", "марта", "апреля", "мая", "июня",
    "июля", "августа", "сентября", "октября", "ноября", "декабря",
)  # fmt: skip
OUTCOME = {
    "offer": "предложение на запрошенных условиях",
    "counteroffer": "предложение на иных условиях",
    "alternative_product": "предложение другого продукта",
    "manual_review": "передана сотруднику банка",
    "info_requested": "запрошены уточнения",
    "declined": "отказ",
}


@dataclass
class Turn:
    """One answer in progress: the messages the model sees and what the tools did."""

    user: AbstractBaseUser
    toolset: Any  # tools or tools_bank: tool_specs(), run_tool()
    messages: list[Message]
    journal: list[dict] = field(default_factory=list)
    pending_action: dict | None = None
    calls: int = 0

    def run(self, client) -> str:
        specs = self.toolset.tool_specs()
        allowed = {spec.name for spec in specs}
        for _step in range(settings.LLM_MAX_STEPS):
            response = client.complete(self.messages, specs)
            if not response.tool_calls:
                return response.content
            self.messages.append(
                Message(role="assistant", content=response.content, tool_calls=response.tool_calls)
            )
            for call in response.tool_calls:
                result = self._execute(allowed, call.name, call.arguments)
                self.journal.append({"name": call.name, "arguments": call.arguments,
                                     "result": result})  # fmt: skip
                if isinstance(result.get("pending_action"), dict):
                    self.pending_action = result["pending_action"]
                self.messages.append(
                    Message(role="tool", content=json.dumps(result, ensure_ascii=False),
                            tool_call_id=call.id)
                )  # fmt: skip
        return STEPS_EXCEEDED

    def _execute(self, allowed: set[str], name: str, arguments: dict) -> dict:
        refusal = guards.check_tool_call(allowed, name, self.calls)
        if refusal is not None:
            return {"error": {"code": "refused", "message": refusal}}
        self.calls += 1
        started = time.monotonic()
        try:
            result = self.toolset.run_tool(self.user, name, arguments)
        except Exception:  # a bug in a tool must not cost the user the whole answer
            logger.exception("assistant tool %s failed", name)
            result = {"error": {"code": "internal", "message": "Не получилось получить данные."}}
        logger.info(
            "assistant tool %s",
            name,
            extra={
                "kind": "assistant_tool",
                "source": name,
                "status": result["error"]["code"] if "error" in result else "ok",
                "duration_ms": round((time.monotonic() - started) * 1000, 1),
            },
        )
        return result


# ───────────────────────── public interface (И1, И2а) ─────────────────────────


def reply(
    user: AbstractBaseUser, profile: Profile, text: str, application_id: int | None = None
) -> dict:
    """One answer in the shape of AssistantReply: {reply, tool_calls, pending_action}."""
    toolset = _toolset(profile)
    application = _application(user, profile, application_id)
    tokens = context.bind(user_id=user.pk, application_id=application.pk if application else None)
    try:
        checked = guards.check_input(text)
        if checked.refusal is not None:
            return _save(user, application, checked.text or text[:2000], checked.refusal, [], None)
        system = prompts.load(profile).render(
            today=_today(),
            user_name=_user_name(user),
            application_context=_context(user, profile, application),
        )
        turn = Turn(
            user=user,
            toolset=toolset,
            messages=[
                Message(role="system", content=system),
                *_history(user, application),
                Message(role="user", content=checked.text),
            ],
        )
        try:
            answer = turn.run(get_llm_client())
        except LLMError as error:
            # The mock goes on from where the provider stopped: tools already run are not
            # repeated, the answer is made of their results (or the mock calls the tools).
            logger.warning("assistant provider failed, answering with the mock: %s", error)
            try:
                answer = f"{UNAVAILABLE} {turn.run(MockLLMClient())}"
            except Exception:
                logger.exception("assistant mock fallback failed")
                answer = UNAVAILABLE_ONLY
        reply_text = guards.check_output(answer) or UNAVAILABLE_ONLY
        return _save(user, application, checked.text, reply_text, turn.journal, turn.pending_action)
    finally:
        context.reset(tokens)


def summary(user: AbstractBaseUser, application_id: int) -> dict:
    """«Сводка для решения» (И2а, AssistantSummary): risks, to_verify, draft_comment, sources."""
    answer = reply(user, "bank", SUMMARY_REQUEST, application_id)
    parsed = summary_module.parse(answer["reply"])
    if parsed is not None:
        return parsed
    results = {
        call["name"]: call["result"]
        for call in answer["tool_calls"]
        if isinstance(call.get("result"), dict) and "error" not in call["result"]
    }
    for name in SUMMARY_TOOLS:  # the model skipped them: the facts are read directly
        if name not in results:
            result = tools_bank.run_tool(user, name, {"application_id": application_id})
            if "error" not in result:
                results[name] = result
    return summary_module.from_facts(results)


# ───────────────────────── helpers ─────────────────────────


def _toolset(profile: str):
    if profile == "client":
        return tools
    if profile == "bank":
        return tools_bank
    raise ValueError(f"unknown assistant profile: {profile!r}")


def _application(user: AbstractBaseUser, profile: str, application_id: int | None):
    """Client: their own application or none; bank: a bank user and an existing application.
    The wrong side or someone else's application is «not found», as on every endpoint."""
    if profile == "client":
        if is_bank_user(user):
            raise NotFound(NOT_FOUND)
        return None if application_id is None else get_client_application(user, application_id)
    if not is_bank_user(user):
        raise NotFound(NOT_FOUND)
    if application_id is None:
        raise ValidationError({"application_id": ["Ассистент сотрудника работает по заявке."]})
    application = (
        Application.objects.select_related("company", "product").filter(pk=application_id).first()
    )
    if application is None:
        raise NotFound(NOT_FOUND)
    return application


def _history(user: AbstractBaseUser, application: Application | None) -> list[Message]:
    """The last messages of this dialogue (same user, same application), oldest first."""
    rows = (
        AssistantMessage.objects.filter(user=user, application=application)
        .exclude(role=MessageRole.TOOL)
        .order_by("-created_at", "-id")[:HISTORY]
    )
    return [Message(role=row.role, content=row.content) for row in reversed(list(rows))]


def _save(user, application, text: str, answer: str, journal: list, pending) -> dict:
    AssistantMessage.objects.create(
        user=user, application=application, role=MessageRole.USER, content=text
    )
    AssistantMessage.objects.create(
        user=user,
        application=application,
        role=MessageRole.ASSISTANT,
        content=answer,
        tool_calls=journal,
    )
    return {"reply": answer, "tool_calls": journal, "pending_action": pending}


def _today() -> str:
    today = timezone.localdate()
    return f"{today.day} {MONTHS[today.month - 1]} {today.year}"


def _user_name(user: AbstractBaseUser) -> str:
    profile = getattr(user, "profile", None)
    return (profile.full_name if profile else "") or user.get_full_name() or user.get_username()


def _context(user: AbstractBaseUser, profile: str, application: Application | None) -> str:
    """{application_context}: the application in a few lines; typed text fenced; ≤ 1500 chars."""
    lines: list[str] = []
    if application is None:
        latest = client_applications(user).order_by("-created_at", "-id").first()
        lines.append(
            "Заявка не выбрана."
            + (f" Последняя заявка пользователя — номер {latest.pk}." if latest else "")
        )
        membership = user.memberships.select_related("company").first()
        if membership:
            company = membership.company
            lines.append(guards.wrap_untrusted("Компания", company.short_name or company.name))
        return "\n".join(line for line in lines if line)[:CONTEXT_LIMIT]

    product = application.product
    lines.append(
        f"Заявка №{application.pk}: статус «{tools.STATUS_TEXT[application.status][0]}»; "
        f"продукт {product.name if product else 'не выбран'}; "
        f"запрошено {rubles(application.requested_amount)} на {application.term_months} мес."
    )
    decision = application.decisions.order_by("-created_at", "-id").first()
    if decision is not None:
        who = "предварительная оценка" if decision.decided_by == "auto" else "сотрудник банка"
        grade = f", грейд {decision.grade}" if decision.grade else ""
        lines.append(f"Решение ({who}): {OUTCOME.get(decision.outcome, decision.outcome)}{grade}.")
    offer = current_offer(application)
    if offer is not None:
        payment = (
            f", платёж {rubles(offer.monthly_payment)} в месяц" if offer.monthly_payment else ""
        )
        lines.append(
            f"Предложение: {offer.product.name}, {rubles(offer.amount)} на {offer.term_months} мес "
            f"под {_percent(offer.rate)}{payment}."
        )
    company = application.company
    if profile == "bank":
        lines.append(f"Компания: ИНН {company.inn}, форма {company.legal_form}.")
    lines.append(guards.wrap_untrusted("Название компании", company.short_name or company.name))
    lines.append(guards.wrap_untrusted("Цель", application.purpose))
    return "\n".join(line for line in lines if line)[:CONTEXT_LIMIT]


def _percent(fraction) -> str:
    value = (fraction * 100).normalize()
    return f"{value:f}".replace(".", ",") + " %"
