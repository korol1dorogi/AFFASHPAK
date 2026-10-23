"""Client assistant tools (AI1, AI18): the only way the client's model touches data (И3).

Every tool runs on behalf of the current user through the same services and serializers as the
API: their company only, a foreign application is «not found», bank users get nothing here (the
bank has its own read-only set, tools_bank.py). Tools never compute money themselves
(credit_math and the recommendation service do), never change a status and never submit:
`create_draft` only proposes a PendingAction that a human confirms.

Shared mechanics — validation, error format, `client_text` — are in tools_common.py.
"""

from datetime import timedelta
from typing import Any

from django.contrib.auth.models import AbstractBaseUser
from django.db import transaction
from django.utils import timezone
from rest_framework import serializers
from rest_framework.exceptions import APIException, NotFound, ValidationError

from apps.applications import services
from apps.applications.access import (
    NOT_FOUND,
    actor_for,
    client_applications,
    current_membership,
    get_client_application,
    is_bank_user,
)
from apps.applications.models import Application, InfoRequestStatus, NeedType
from apps.applications.offers import current_offer
from apps.applications.serializers import (
    ApplicationCreateSerializer,
    DecisionSerializer,
    FinancialSnapshotSerializer,
)
from apps.applications.transitions import available_actions
from apps.assistant import glossary
from apps.assistant.llm.base import ToolSpec
from apps.assistant.models import PendingAction, PendingActionKind, PendingActionStatus
from apps.assistant.tools_common import (
    APPLICATION_ID,
    MONEY,
    ApplicationRefSerializer,
    Tool,
    money,
    registry,
    run_registry,
    validated,
)
from apps.business.metrics import company_metrics as metrics_of
from apps.credit_math import annuity_summary
from apps.documents.models import DocumentKind
from apps.pipeline.decide import SOURCE_NAME
from apps.products.models import Product
from apps.products.views import AnnuityRequestSerializer
from apps.recommendations.api import recommend_for_user, what_if_for_user
from apps.recommendations.serializers import ReasonSerializer
from apps.recommendations.service import latest_snapshot
from apps.scoring.texts import rubles

PENDING_TTL = timedelta(minutes=30)
PRELIMINARY = "Это предварительная оценка, а не решение банка."

# What a status means and what happens next — the same words as the client sees
# (docs/state-machine.md, frontend/src/texts STATUS).
STATUS_TEXT: dict[str, tuple[str, str, str]] = {
    "draft": (
        "Черновик",
        "Заявка ещё не отправлена в банк.",
        "Проверьте данные и отправьте заявку — черновик сохраняется сам.",
    ),
    "submitted": (
        "Отправлена",
        "Заявка в банке, скоро начнётся проверка.",
        "Ничего делать не нужно — обновим статус сами.",
    ),
    "processing": (
        "Проверяем",
        "Проверяем данные в реестрах, кредитной истории и по счёту.",
        "Обычно это занимает до минуты.",
    ),
    "manual_review": (
        "У сотрудника банка",
        "Заявку смотрит сотрудник банка.",
        "Обычно это занимает до одного дня. Если понадобятся документы, пришлём уведомление.",
    ),
    "info_requested": (
        "Нужны уточнения",
        "Банку не хватает данных или документа.",
        "Ответьте на запрос в заявке — без этого проверка не продолжится.",
    ),
    "offer": (
        "Есть предложение",
        "Банк готов дать деньги на условиях из предложения.",
        "Примите предложение, чтобы перейти к подписанию, или откажитесь.",
    ),
    "signing": (
        "Подписание",
        "Предложение принято, осталось подписать договор.",
        "Подпишите договор кодом, который покажем на экране.",
    ),
    "signed": (
        "Договор подписан",
        "Договор подписан, деньги отправляем на счёт.",
        "Обычно деньги приходят в течение нескольких минут.",
    ),
    "issued": (
        "Деньги выданы",
        "Деньги поступили на счёт.",
        "Готово. График платежей — в разделе заявки.",
    ),
    "declined": (
        "Отказ",
        "Сейчас банк не может дать деньги.",
        "Посмотрите причины и что можно улучшить — затем подайте заявку снова.",
    ),
    "cancelled": (
        "Отозвана",
        "Заявка отозвана.",
        "Чтобы получить деньги, подберите финансирование заново.",
    ),
}

OUTCOME_TEXT = {
    "offer": "предложение на запрошенных условиях",
    "counteroffer": "предложение на иных условиях",
    "alternative_product": "предложение другого продукта",
    "manual_review": "заявку передали сотруднику банка — это не отказ",
    "info_requested": "банк просит уточнить данные",
    "declined": "отказ",
}

# A check status for the client: what it means and what to do (SRC2; SRC3 «нет данных не значит
# плохо»). No source data, hashes or versions here — those are the bank's (tools_bank.py).
CHECK_FOR_CLIENT: dict[str, tuple[str, str | None]] = {
    "ok": ("данные получены", None),
    "warning": ("есть замечания", "Сотрудник банка посмотрит их сам; если нужно, пришлёт запрос."),
    "failed": ("проверка не пройдена", "Причины — в решении по заявке."),
    "unavailable": (
        "источник не ответил",
        "Ничего делать не нужно: данные проверит сотрудник банка. Это не отказ.",
    ),
    "not_found": ("компанию не нашли в реестре", "Проверьте ИНН в профиле компании."),
    "restricted": (
        "сведения в источнике скрыты",
        "Банк может попросить подтверждающие документы — ответьте на запрос в заявке. "
        "Это не отказ.",
    ),
    "consent_missing": (
        "не запрашивали: нет согласия на запрос в бюро кредитных историй",
        "Кредитную историю проверит сотрудник банка. В новой заявке согласие даётся при отправке.",
    ),
}
NOT_CONNECTED = (
    "счёт не подключён",
    "Подключите выписку по счёту в профиле компании — тогда оценка будет точнее.",
)


# ───────────────────────── helpers ─────────────────────────


def _client_only(user: AbstractBaseUser) -> None:
    """Client tools are for clients; the bank's assistant has its own read-only set."""
    if is_bank_user(user):
        raise NotFound(NOT_FOUND)


def _application(user: AbstractBaseUser, application_id: int | None) -> Application:
    """The given application of the user, or their latest one. Foreign → not found."""
    _client_only(user)
    if application_id is not None:
        return get_client_application(user, application_id)
    latest = client_applications(user).order_by("-created_at", "-id").first()
    if latest is None:
        raise NotFound("Заявок пока нет.")
    return latest


def _latest_decision(application: Application):
    return application.decisions.order_by("-created_at", "-id").first()


def _document_names(kinds) -> list[dict]:
    labels = dict(DocumentKind.choices)
    return [{"kind": kind, "name": labels.get(kind, kind)} for kind in kinds]


# ───────────────────────── AI1: pick, count, explain, draft ─────────────────────────


def recommend_products(user: AbstractBaseUser, arguments: dict) -> dict:
    """D6: the same recommendation service and serializer as POST /api/recommendations."""
    _client_only(user)
    result = recommend_for_user(user, arguments)
    return {**result, "note": PRELIMINARY}


def calc_payment(user: AbstractBaseUser, arguments: dict) -> dict:
    """Annuity from credit_math — the model never does the arithmetic itself."""
    data = validated(AnnuityRequestSerializer, arguments)
    if data["annual_rate"] > 1:
        # Models send percent («24») for a fraction; the calculator would count 2400 %.
        raise ValidationError({"annual_rate": ["Ставка — годовая доля: 24 % передайте как 0.24."]})
    summary = annuity_summary(data["principal"], data["annual_rate"], data["term_months"])
    return {
        "principal": money(data["principal"]),
        "annual_rate": money(data["annual_rate"]),
        "term_months": data["term_months"],
        "payment": money(summary.payment),
        "total_paid": money(summary.total_paid),
        "overpayment": money(summary.overpayment),
    }


def explain_status(user: AbstractBaseUser, arguments: dict) -> dict:
    data = validated(ApplicationRefSerializer, arguments)
    application = _application(user, data.get("application_id"))
    actor = actor_for(user, application)
    label, meaning, next_step = STATUS_TEXT[application.status]
    requests = application.info_requests.filter(status=InfoRequestStatus.OPEN)
    return {
        "application_id": application.pk,
        "status": application.status,
        "status_label": label,
        "meaning": meaning,
        "next_step": next_step,
        "available_actions": available_actions(application, actor),
        "open_info_requests": [
            {
                "message": request.message,  # written by the bank officer
                "document_kinds": _document_names(request.document_kinds),
            }
            for request in requests
        ],
    }


def explain_decision(user: AbstractBaseUser, arguments: dict) -> dict:
    data = validated(ApplicationRefSerializer, arguments)
    application = _application(user, data.get("application_id"))
    decision = _latest_decision(application)
    if decision is None:
        return {
            "application_id": application.pk,
            "decision": None,
            "message": "Решения по заявке пока нет.",
        }
    offer = current_offer(application)
    is_preliminary = decision.decided_by == "auto"
    return {
        "application_id": application.pk,
        "decision": {
            "outcome": decision.outcome,
            "outcome_text": OUTCOME_TEXT.get(decision.outcome, decision.outcome),
            "is_preliminary": is_preliminary,
            "reasons": decision.reasons,
            "improvements": list(decision.improvements),
            "comment": decision.comment,
        },
        "offer": None
        if offer is None
        else {
            "product": offer.product.name,
            "amount": money(offer.amount),
            "requested_amount": money(offer.requested_amount),
            "term_months": offer.term_months,
            "rate": money(offer.rate),
            "monthly_payment": money(offer.monthly_payment),
            "is_counteroffer": offer.is_counteroffer,
            "product_changed": offer.product_changed,
        },
        "note": PRELIMINARY if is_preliminary else "Решение принял сотрудник банка.",
    }


def create_draft(user: AbstractBaseUser, arguments: dict) -> dict:
    """Proposes a draft — nothing is created until the human confirms (confirm_pending_action)."""
    _client_only(user)
    if current_membership(user) is None:
        raise NotFound("Сначала добавьте компанию.")
    payload = {**arguments, "prefill_source": "assistant"}
    data = validated(ApplicationCreateSerializer, payload)
    if (
        data.get("product_code")
        and not Product.objects.filter(code=data["product_code"], is_active=True).exists()
    ):
        raise ValidationError({"product_code": ["Такого продукта нет в каталоге."]})
    action = PendingAction.objects.create(
        user=user,
        kind=PendingActionKind.CREATE_APPLICATION,
        payload=ApplicationCreateSerializer(data).data,  # JSON-safe: decimals as strings
        summary=_draft_summary(data),
        expires_at=timezone.now() + PENDING_TTL,
    )
    return {"pending_action": pending_action_dict(action)}


# ───────────────────────── AI18: what if, plan, checks, metrics, documents, terms ──────────


class WhatIfArgumentsSerializer(serializers.Serializer):
    application_id = serializers.IntegerField(min_value=1, required=False)
    amount = serializers.DecimalField(max_digits=14, decimal_places=2, min_value=1)
    term_months = serializers.IntegerField(min_value=1, max_value=360)


def what_if(user: AbstractBaseUser, arguments: dict) -> dict:
    """XP1: another amount or term for the active offer — the service of the «Что если» slider,
    with the same refusals (no offer with a fixed payment → conflict, term outside → invalid)."""
    data = validated(WhatIfArgumentsSerializer, arguments)
    application = _application(user, data.get("application_id"))
    payload = {"amount": money(data["amount"]), "term_months": data["term_months"]}
    result = what_if_for_user(user, application.pk, payload)
    return {"application_id": application.pk, **result, "note": PRELIMINARY}


def approval_plan(user: AbstractBaseUser, arguments: dict) -> dict:
    """XP2: the steps to grade C after a decline by grade — from the stored decision and score,
    exactly what the decision card shows; nothing is recounted here."""
    data = validated(ApplicationRefSerializer, arguments)
    application = _application(user, data.get("application_id"))
    decision = _latest_decision(application)
    if decision is None:
        return {"application_id": application.pk, "plan": None, "message": "Решения пока нет."}
    serialized = DecisionSerializer(decision).data
    plan = serialized.get("approval_plan")
    result = {
        "application_id": application.pk,
        "outcome": decision.outcome,
        "grade": decision.grade,
        "plan": plan,
        "improvements": list(decision.improvements),
    }
    if plan is None:
        result["message"] = (
            "План по баллам строится только после автоматического отказа по грейду. "
            "Что можно улучшить — в списке improvements."
        )
    else:
        result["note"] = PRELIMINARY
    return result


def explain_check_status(user: AbstractBaseUser, arguments: dict) -> dict:
    """SRC2 statuses of the application's checks in plain words, with what to do."""
    data = validated(ApplicationRefSerializer, arguments)
    application = _application(user, data.get("application_id"))
    checks = []
    for check in application.checks.order_by("checked_at", "id"):
        if check.source == "bank_account" and (check.data or {}).get("not_connected"):
            meaning, todo = NOT_CONNECTED
        else:
            meaning, todo = CHECK_FOR_CLIENT.get(check.status, (check.status, None))
        checks.append(
            {
                "source": check.source,
                "source_name": SOURCE_NAME.get(check.source, check.source),
                "status": check.status,
                "meaning": meaning,
                "what_to_do": todo,
            }
        )
    result: dict[str, Any] = {"application_id": application.pk, "checks": checks}
    if not checks:
        result["message"] = (
            "Проверок пока нет: они начинаются после отправки заявки в банк."
            if application.status == "draft"
            else "Проверки по заявке не проводились."
        )
    else:
        result["note"] = "Если данных нет или они скрыты, это не отказ: заявку смотрит сотрудник."
    return result


def company_metrics(user: AbstractBaseUser, arguments: dict) -> dict:
    """The same metrics as GET /api/company/metrics: the user's company, the latest statement."""
    validated(serializers.Serializer, arguments)
    _client_only(user)
    membership = current_membership(user)
    if membership is None:
        raise NotFound("Сначала добавьте компанию.")
    company = membership.company
    snapshot = latest_snapshot(company)
    return {
        "snapshot": FinancialSnapshotSerializer(snapshot).data if snapshot else None,
        "metrics": ReasonSerializer(metrics_of(company, snapshot), many=True).data,
        "message": None
        if snapshot
        else "Выписки по счёту ещё нет — подключите счёт в профиле компании.",
    }


class RequiredDocumentsSerializer(serializers.Serializer):
    application_id = serializers.IntegerField(min_value=1, required=False)
    product_code = serializers.CharField(max_length=64, required=False)


def required_documents(user: AbstractBaseUser, arguments: dict) -> dict:
    """Documents of a product (by its code) or of an application: needed, uploaded, missing, and
    what the bank asked for in open requests."""
    data = validated(RequiredDocumentsSerializer, arguments)
    _client_only(user)
    if "product_code" in data and "application_id" not in data:
        product = Product.objects.filter(code=data["product_code"], is_active=True).first()
        if product is None:
            raise ValidationError({"product_code": ["Такого продукта нет в каталоге."]})
        return {
            "product": product.name,
            "required": _document_names(product.required_documents),
        }
    application = _application(user, data.get("application_id"))
    product = application.product
    required = list(product.required_documents) if product else []
    uploaded = sorted(set(application.documents.values_list("kind", flat=True)))
    requested = [
        kind
        for request in application.info_requests.filter(status=InfoRequestStatus.OPEN)
        for kind in request.document_kinds
    ]
    missing = [kind for kind in dict.fromkeys(required + requested) if kind not in uploaded]
    return {
        "application_id": application.pk,
        "product": product.name if product else None,
        "required": _document_names(required),
        "uploaded": _document_names(uploaded),
        "requested_by_bank": _document_names(dict.fromkeys(requested)),
        "missing": _document_names(missing),
        "message": None if product else "Продукт не выбран — список документов зависит от него.",
    }


class TermSerializer(serializers.Serializer):
    term = serializers.CharField(max_length=80)


def explain_term(user: AbstractBaseUser, arguments: dict) -> dict:
    """A term in plain words from the glossary (docs/domain.md)."""
    data = validated(TermSerializer, arguments)
    _client_only(user)
    found = glossary.lookup(data["term"])
    if found is None:
        raise NotFound(
            "Такого термина нет в словаре. Есть: " + ", ".join(sorted(glossary.TERMS)) + "."
        )
    term, explanation = found
    return {"term": term, "explanation": explanation}


# ───────────────────────── pending actions ─────────────────────────


def pending_action_dict(action: PendingAction) -> dict:
    """PendingAction of docs/openapi.yaml."""
    return {
        "id": str(action.id),
        "kind": action.kind,
        "summary": action.summary,
        "application_id": action.application_id,
    }


def confirm_pending_action(user: AbstractBaseUser, action_id) -> Application:
    """The human pressed «Подтвердить». Foreign or unknown → 404; used or expired → 409.
    The payload is validated again: the catalog or the user's rights may have changed."""
    _client_only(user)
    with transaction.atomic():
        action = PendingAction.objects.select_for_update().filter(pk=action_id, user=user).first()
        if action is None:
            raise NotFound(NOT_FOUND)
        if action.status != PendingActionStatus.PENDING:
            raise ActionConflict("Это действие уже выполнено.")
        if action.expires_at <= timezone.now():
            raise ActionConflict("Предложение ассистента устарело. Попросите его ещё раз.")
        data = validated(ApplicationCreateSerializer, action.payload)
        application = services.create_application(user, data)
        action.status = PendingActionStatus.DONE
        action.application = application
        action.confirmed_at = timezone.now()
        action.save(update_fields=["status", "application", "confirmed_at"])
        return application


class ActionConflict(APIException):
    status_code = 409
    default_code = "conflict"
    default_detail = "Действие уже выполнено."


# ───────────────────────── registry ─────────────────────────

_REF = {"type": "object", "additionalProperties": False, "properties": APPLICATION_ID}

TOOLS = registry(
    Tool(
        ToolSpec(
            "recommend_products",
            "Подобрать продукты под задачу бизнеса по данным компании пользователя: суммы, "
            "ставки, платёж и причины. Предварительная оценка, не решение банка.",
            {
                "type": "object",
                "required": ["need_type"],
                "additionalProperties": False,
                "properties": {
                    "need_type": {"type": "string", "enum": list(NeedType.values)},
                    "amount": MONEY,
                    "term_months": {"type": "integer", "minimum": 1, "maximum": 360},
                    "invoice_amount": {
                        **MONEY,
                        "description": "Сумма отгрузки по УПД, нужна для receivable_delay",
                    },
                },
            },
        ),
        recommend_products,
    ),
    Tool(
        ToolSpec(
            "calc_payment",
            "Посчитать ежемесячный аннуитетный платёж, общую сумму выплат и переплату.",
            {
                "type": "object",
                "required": ["principal", "annual_rate", "term_months"],
                "additionalProperties": False,
                "properties": {
                    "principal": MONEY,
                    "annual_rate": {
                        "type": "string",
                        "description": "Годовая ставка в долях: 24 % → 0.24",
                    },
                    "term_months": {"type": "integer", "minimum": 1, "maximum": 360},
                },
            },
        ),
        calc_payment,
    ),
    Tool(
        ToolSpec(
            "explain_status",
            "Объяснить статус заявки пользователя простыми словами и что делать дальше.",
            _REF,
        ),
        explain_status,
    ),
    Tool(
        ToolSpec(
            "explain_decision",
            "Объяснить решение по заявке: причины, что улучшить, условия предложения.",
            _REF,
        ),
        explain_decision,
    ),
    Tool(
        ToolSpec(
            "create_draft",
            "Предложить черновик заявки. Он появится только после того, как пользователь "
            "нажмёт «Подтвердить»; отправляет заявку в банк сам пользователь.",
            {
                "type": "object",
                "required": ["need_type", "purpose", "requested_amount", "term_months"],
                "additionalProperties": False,
                "properties": {
                    "need_type": {"type": "string", "enum": list(NeedType.values)},
                    "purpose": {"type": "string", "maxLength": 1000},
                    "requested_amount": MONEY,
                    "term_months": {"type": "integer", "minimum": 1, "maximum": 360},
                    "product_code": {"type": "string"},
                    "invoice_amount": MONEY,
                    "collateral_description": {"type": "string", "maxLength": 1000},
                },
            },
        ),
        create_draft,
    ),
    Tool(
        ToolSpec(
            "what_if",
            "Пересчитать действующее предложение на другую сумму или срок: платёж, проходит ли "
            "по денежному потоку и максимум суммы. Предварительная оценка.",
            {
                "type": "object",
                "required": ["amount", "term_months"],
                "additionalProperties": False,
                "properties": {
                    **APPLICATION_ID,
                    "amount": MONEY,
                    "term_months": {"type": "integer", "minimum": 1, "maximum": 360},
                },
            },
        ),
        what_if,
    ),
    Tool(
        ToolSpec(
            "approval_plan",
            "План «как получить одобрение» после отказа: какие показатели и до какого значения "
            "улучшить, сколько баллов это даст.",
            _REF,
        ),
        approval_plan,
    ),
    Tool(
        ToolSpec(
            "explain_check_status",
            "Статусы проверок заявки (реестр, ФНС, кредитная история, счёт) простыми словами и "
            "что делать.",
            _REF,
        ),
        explain_check_status,
    ),
    Tool(
        ToolSpec(
            "company_metrics",
            "Показатели компании пользователя по выписке: обороты, денежный поток, долговая "
            "нагрузка, тренд выручки, зависимость от покупателей.",
            {"type": "object", "additionalProperties": False, "properties": {}},
        ),
        company_metrics,
    ),
    Tool(
        ToolSpec(
            "required_documents",
            "Какие документы нужны: для продукта (по коду) или для заявки — что загружено, "
            "чего не хватает, что просит банк.",
            {
                "type": "object",
                "additionalProperties": False,
                "properties": {**APPLICATION_ID, "product_code": {"type": "string"}},
            },
        ),
        required_documents,
    ),
    Tool(
        ToolSpec(
            "explain_term",
            "Объяснить банковский термин простыми словами (овердрафт, факторинг, DSCR, грейд, "
            "БКИ и другие).",
            {
                "type": "object",
                "required": ["term"],
                "additionalProperties": False,
                "properties": {"term": {"type": "string", "maxLength": 80}},
            },
        ),
        explain_term,
    ),
)


def tool_specs() -> list[ToolSpec]:
    return [tool.spec for tool in TOOLS.values()]


def run_tool(user: AbstractBaseUser, name: str, arguments: Any) -> dict:
    """Run one client tool as `user`. Errors come back as data for the model, never raised."""
    return run_registry(TOOLS, user, name, arguments)


def _draft_summary(data: dict) -> str:
    product = Product.objects.filter(code=data.get("product_code")).first()
    what = f"«{product.name}»" if product else "продукт подберёт банк"
    return (
        f"Создать черновик заявки: {rubles(data['requested_amount'])} "
        f"на {data['term_months']} мес, {what}. Цель: {data['purpose']}. "
        "Отправите заявку в банк вы сами после проверки."
    )
