"""Assistant tools (AI1): the only way the model touches data.

Every tool runs on behalf of the current user through the same services and serializers as the
API: their company only, a foreign application is «not found», bank users get nothing. Arguments
come from the model, so they are untrusted and validated like a request body. Tools never
compute money themselves (credit_math and the recommendation service do), never change a status
and never submit: `create_draft` only proposes a PendingAction that a human confirms.

`run_tool` never raises on a bad call: the model gets `{"error": {code, message}}` and can tell
the user what went wrong. Each result is plain JSON for the journal (AssistantMessage.tool_calls).
"""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal
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
from apps.applications.serializers import ApplicationCreateSerializer
from apps.applications.transitions import available_actions
from apps.assistant.llm.base import ToolSpec
from apps.assistant.models import PendingAction, PendingActionKind, PendingActionStatus
from apps.credit_math import annuity_summary
from apps.products.models import Product
from apps.products.views import AnnuityRequestSerializer
from apps.recommendations.api import recommend_for_user
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


# ───────────────────────── arguments: untrusted, they come from the model ─────────────────


class ApplicationRefSerializer(serializers.Serializer):
    application_id = serializers.IntegerField(min_value=1, required=False)


def _validated(serializer_class: type[serializers.Serializer], arguments: dict) -> dict:
    """additionalProperties: false — an unknown argument («status», «approved_amount»…) is an
    error, not silently ignored."""
    serializer = serializer_class(data=arguments)
    unknown = sorted(set(arguments) - set(serializer.fields))
    if unknown:
        raise ValidationError({name: ["Неизвестное поле."] for name in unknown})
    serializer.is_valid(raise_exception=True)
    return serializer.validated_data


def _client_only(user: AbstractBaseUser) -> None:
    """The assistant has no bank-side tools (AGENTS.md, security 5)."""
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


# ───────────────────────── tools ─────────────────────────


def recommend_products(user: AbstractBaseUser, arguments: dict) -> dict:
    """D6: the same recommendation service and serializer as POST /api/recommendations."""
    _client_only(user)
    result = recommend_for_user(user, arguments)
    return {**result, "note": PRELIMINARY}


def calc_payment(user: AbstractBaseUser, arguments: dict) -> dict:
    """Annuity from credit_math — the model never does the arithmetic itself."""
    data = _validated(AnnuityRequestSerializer, arguments)
    summary = annuity_summary(data["principal"], data["annual_rate"], data["term_months"])
    return {
        "principal": _money(data["principal"]),
        "annual_rate": format(data["annual_rate"], "f"),
        "term_months": data["term_months"],
        "payment": _money(summary.payment),
        "total_paid": _money(summary.total_paid),
        "overpayment": _money(summary.overpayment),
    }


def explain_status(user: AbstractBaseUser, arguments: dict) -> dict:
    data = _validated(ApplicationRefSerializer, arguments)
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
            {"message": request.message, "document_kinds": list(request.document_kinds)}
            for request in requests
        ],
    }


def explain_decision(user: AbstractBaseUser, arguments: dict) -> dict:
    data = _validated(ApplicationRefSerializer, arguments)
    application = _application(user, data.get("application_id"))
    decision = application.decisions.order_by("-created_at", "-id").first()
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
            "amount": _money(offer.amount),
            "requested_amount": _money(offer.requested_amount),
            "term_months": offer.term_months,
            "rate": format(offer.rate, "f"),
            "monthly_payment": None
            if offer.monthly_payment is None
            else _money(offer.monthly_payment),
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
    data = _validated(ApplicationCreateSerializer, payload)
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
        data = _validated(ApplicationCreateSerializer, action.payload)
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


@dataclass(frozen=True)
class Tool:
    spec: ToolSpec
    run: Callable[[AbstractBaseUser, dict], dict]


_APPLICATION_ID = {
    "application_id": {
        "type": "integer",
        "minimum": 1,
        "description": "Номер заявки. Не указан — последняя заявка пользователя.",
    }
}
_MONEY = {
    "type": "string",
    "pattern": r"^\d+(\.\d{1,2})?$",
    "description": "Рубли, например 900000.00",
}

TOOLS: dict[str, Tool] = {
    tool.spec.name: tool
    for tool in (
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
                        "amount": _MONEY,
                        "term_months": {"type": "integer", "minimum": 1, "maximum": 360},
                        "invoice_amount": {
                            **_MONEY,
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
                        "principal": _MONEY,
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
                {"type": "object", "additionalProperties": False, "properties": _APPLICATION_ID},
            ),
            explain_status,
        ),
        Tool(
            ToolSpec(
                "explain_decision",
                "Объяснить решение по заявке: причины, что улучшить, условия предложения.",
                {"type": "object", "additionalProperties": False, "properties": _APPLICATION_ID},
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
                        "requested_amount": _MONEY,
                        "term_months": {"type": "integer", "minimum": 1, "maximum": 360},
                        "product_code": {"type": "string"},
                        "invoice_amount": _MONEY,
                        "collateral_description": {"type": "string", "maxLength": 1000},
                    },
                },
            ),
            create_draft,
        ),
    )
}


def tool_specs() -> list[ToolSpec]:
    return [tool.spec for tool in TOOLS.values()]


def run_tool(user: AbstractBaseUser, name: str, arguments: Any) -> dict:
    """Run one tool as `user`. Errors come back as data for the model, never as an exception."""
    tool = TOOLS.get(name)
    if tool is None:
        return _error("unknown_tool", "Такого инструмента нет.")
    if not isinstance(arguments, dict):
        return _error("invalid", "Аргументы должны быть объектом.")
    try:
        return tool.run(user, arguments)
    except ValidationError as exc:
        return {"error": {"code": "invalid", "message": "Проверьте данные.", "details": exc.detail}}
    except APIException as exc:
        return _error(exc.default_code, str(exc.detail))


def _error(code: str, message: str) -> dict:
    return {"error": {"code": code, "message": message}}


def _money(value: Decimal) -> str:
    return format(value, "f")


def _draft_summary(data: dict) -> str:
    product = Product.objects.filter(code=data.get("product_code")).first()
    what = f"«{product.name}»" if product else "продукт подберёт банк"
    return (
        f"Создать черновик заявки: {rubles(data['requested_amount'])} "
        f"на {data['term_months']} мес, {what}. Цель: {data['purpose']}. "
        "Отправите заявку в банк вы сами после проверки."
    )
