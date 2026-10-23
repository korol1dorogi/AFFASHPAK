"""Bank officer assistant tools (AI17, interface И3): read only, bank_manager only.

The same shape as the client set (tools.py): `tool_specs()`, `run_tool(user, name, args)`, errors
as data. Every tool only reads — the status, the decision and the comment are changed by the
officer in the card, never here; a test runs every tool and finds no INSERT, UPDATE or DELETE.
A client (or anyone who is not a bank user) gets «not found» from every tool, an unknown
application too.

Figures come from what the pipeline stored — Decision.reasons, Score, Check — so the assistant
says exactly what the bank card shows; what the pipeline did not store is counted by credit_math.
«No data» is not a negative (SRC3): no answer, hidden data or no consent mean «ask or check by
hand», never «decline».
"""

from datetime import date
from decimal import Decimal
from typing import Any

from django.contrib.auth.models import AbstractBaseUser
from django.utils import timezone
from rest_framework import serializers
from rest_framework.exceptions import NotFound

from apps.applications.access import NOT_FOUND, is_bank_user
from apps.applications.completeness import field_gaps
from apps.applications.models import Application, InfoRequestStatus, Score
from apps.applications.offers import current_offer
from apps.applications.serializers import user_ref
from apps.applications.sla import sla_state
from apps.assistant.llm.base import ToolSpec
from apps.assistant.tools import STATUS_TEXT
from apps.assistant.tools_common import (
    BANK_APPLICATION_ID,
    BankApplicationSerializer,
    Tool,
    client_text,
    money,
    registry,
    run_registry,
    validated,
)
from apps.credit_math import Metric, debt_to_ebitda, dscr
from apps.documents.models import DocumentKind
from apps.pipeline.decide import SOURCE_NAME
from apps.recommendations.service import latest_snapshot
from apps.scoring.age import business_age_months
from apps.scoring.plan import approval_plan
from apps.scoring.policy import get_policy, get_scorecard
from apps.scoring.texts import rubles

# What a check status means for the decision (SRC2, SRC3).
CHECK_MEANING = {
    "ok": "данные получены",
    "warning": "есть замечания — учтены в скоринге",
    "failed": "проверка не пройдена",
    "unavailable": "источник не ответил — нет данных, это не негатив: проверить вручную",
    "not_found": "компании нет в реестре — стоп-фактор С2, проверить ИНН",
    "restricted": "сведения скрыты — не негатив: запросить документы или проверить вручную",
    "consent_missing": "бюро не запрашивали: нет согласия клиента — не негатив, проверить вручную",
}
# Stop factors (decision-model.md, С1–С6): the metric of their Reason.
STOP_METRICS = {
    "registry_status": "С1 ликвидация или банкротство",
    "egrul_found": "С2 нет в реестре",
    "ebitda": "С3 нет операционной прибыли",
    "bki_current_overdue_days": "С4 текущая просрочка",
    "business_age_months": "С5 бизнес моложе минимума",
    "accounts_suspended": "С6 блокировка счетов",
}
# Figures the pipeline stores in Decision.reasons that the officer weighs for the amount.
LIMIT_METRICS = (
    "max_loan_by_dscr",
    "dscr_after",
    "overdraft_limit",
    "factoring_advance",
    "factoring_commission",
    "working_capital_need",
)
FACTORS = (
    "business_age_months",
    "dscr",
    "debt_to_ebitda",
    "revenue_trend",
    "counterparty_concentration",
    "bki_history",
    "transparent_business",
)
GRADE_ZONES = {
    "A": "автоматическое предложение",
    "B": "автоматическое предложение",
    "C": "ручное рассмотрение",
    "D": "ручное рассмотрение",
    "E": "отказ по грейду",
}
# What to ask the client for when a source said nothing useful (SRC3: ask, do not decline).
ASK_FOR = {
    ("egrul", "unavailable"): "Выписку из ЕГРЮЛ/ЕГРИП не старше 30 дней",
    ("egrul", "not_found"): "Проверить ИНН; выписку из ЕГРЮЛ/ЕГРИП",
    ("transparent_business", "unavailable"): "Справку ФНС об отсутствии задолженности по налогам",
    ("transparent_business", "restricted"): "Справку ФНС об отсутствии задолженности по налогам",
    ("bki", "unavailable"): "Кредитный отчёт из БКИ от клиента или повторный запрос позже",
    ("bki", "restricted"): "Кредитный отчёт из БКИ от клиента",
    ("bki", "consent_missing"): "Согласие на запрос в БКИ или кредитный отчёт клиента",
    ("bank_account", "unavailable"): "Выписку по расчётному счёту за 12 месяцев",
}
# The officer's PRELIMINARY intent for the comment draft → how the draft states the leaning.
INTENTS = {
    "approve": "к одобрению на запрошенных условиях",
    "counteroffer": "к предложению иных условий",
    "request_info": "к запросу недостающих сведений у клиента",
    "decline": "к отказу",
}


# ───────────────────────── helpers ─────────────────────────


def _bank_application(user: AbstractBaseUser, arguments: dict) -> Application:
    """Only a bank user, only an existing application; anything else is «not found»."""
    data = validated(BankApplicationSerializer, arguments)
    if not is_bank_user(user):
        raise NotFound(NOT_FOUND)
    application = (
        Application.objects.select_related("company", "product", "assignee__profile")
        .filter(pk=data["application_id"])
        .first()
    )
    if application is None:
        raise NotFound(NOT_FOUND)
    return application


def _decision(application: Application):
    return application.decisions.order_by("-created_at", "-id").first()


def _reasons(decision) -> dict[str, dict]:
    return {} if decision is None else {r["metric"]: r for r in decision.reasons}


def _iso(value) -> str | None:
    return None if value is None else value.isoformat()


def _kinds(kinds) -> list[dict]:
    labels = dict(DocumentKind.choices)
    return [{"kind": kind, "name": labels.get(kind, kind)} for kind in kinds]


def _metric(value: Metric) -> dict:
    return {"value": money(value.value), "note": value.note}


def _max_points(card, name: str) -> int | None:
    rule = getattr(card, name, None)
    if rule is None:
        return None
    scale = getattr(rule, "scale", None)
    return scale.max_points if scale is not None else getattr(rule, "max_points", None)


def _policy(version: str | None):
    """The policy the decision was made under; an unknown (older) version → the current one."""
    try:
        return get_policy(version) if version else get_policy()
    except KeyError:
        return get_policy()


def _scorecard(version: str):
    try:
        return get_scorecard(version)
    except KeyError:
        return get_scorecard()


def _age(application: Application) -> int | None:
    registered = application.company.registered_at
    on_date: date = (application.submitted_at or timezone.now()).date()
    return None if registered is None else business_age_months(registered, on_date)


# ───────────────────────── tools ─────────────────────────


def application_summary(user: AbstractBaseUser, arguments: dict) -> dict:
    """The whole application in one look: terms, company, status and SLA, decision, offer."""
    application = _bank_application(user, arguments)
    company = application.company
    product = application.product
    decision = _decision(application)
    offer = current_offer(application)
    sla = sla_state(application.status, application.status_changed_at, timezone.now())
    open_requests = application.info_requests.filter(status=InfoRequestStatus.OPEN)
    hours = int((timezone.now() - application.status_changed_at).total_seconds() // 3600)
    return {
        "application_id": application.pk,
        "status": application.status,
        "status_label": STATUS_TEXT[application.status][0],
        "hours_in_status": hours,
        "sla": {
            "due_at": _iso(sla.due_at),
            "is_overdue": sla.is_overdue,
            "overdue_hours": sla.overdue_hours,
        },
        "need_type": application.need_type,
        "product": None
        if product is None
        else {"code": product.code, "name": product.name, "kind": product.kind},
        "requested_amount": money(application.requested_amount),
        "term_months": application.term_months,
        "invoice_amount": money(application.invoice_amount),
        "submitted_at": _iso(application.submitted_at),
        "assignee": user_ref(application.assignee),
        "company": {
            "inn": company.inn,
            "legal_form": company.legal_form,
            "okved": company.okved,
            "region": company.region,
            "registry_status": company.registry_status,
            "business_age_months": _age(application),
            "is_demo": company.is_demo,
        },
        "decision": None
        if decision is None
        else {
            "outcome": decision.outcome,
            "decided_by": decision.decided_by,
            "is_preliminary": decision.decided_by == "auto",
            "grade": decision.grade,
            "policy_version": decision.policy_version,
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
            "status": offer.status,
            "expires_at": _iso(offer.expires_at),
        },
        "checks": {check.source: check.status for check in application.checks.all()},
        "open_info_requests": [
            {"message": request.message, "document_kinds": _kinds(request.document_kinds)}
            for request in open_requests
        ],
        "documents": _kinds(sorted(set(application.documents.values_list("kind", flat=True)))),
        "client_text": client_text(
            company_name=company.name,
            company_short_name=company.short_name,
            okved_name=company.okved_name,
            purpose=application.purpose,
            collateral_description=application.collateral_description,
        ),
    }


def checks_with_provenance(user: AbstractBaseUser, arguments: dict) -> dict:
    """Every source: status and what it means for the decision, the data, when it came (SRC4)."""
    application = _bank_application(user, arguments)
    checks = [
        {
            "source": check.source,
            "source_name": SOURCE_NAME.get(check.source, check.source),
            "status": check.status,
            "meaning": CHECK_MEANING.get(check.status, check.status),
            "summary": check.summary,
            "data": check.data,
            "received_at": _iso(check.received_at),
            "response_sha256": (check.response_sha256 or "")[:12] or None,
            "simulator_version": check.simulator_version,
            "duration_ms": check.duration_ms,
        }
        for check in application.checks.order_by("checked_at", "id")
    ]
    result: dict[str, Any] = {"application_id": application.pk, "checks": checks}
    if not checks:
        result["message"] = (
            "Проверок нет: заявка не отправлена или остановлена до запроса источников "
            "(стоп-фактор по анкете)."
        )
    result["note"] = (
        "Нет ответа, скрытые сведения и отсутствие согласия — не негатив: "
        "запросить документы или проверить вручную (SRC3)."
    )
    return result


def score_breakdown(user: AbstractBaseUser, arguments: dict) -> dict:
    """The scorecard: every factor with its value, points of the maximum, threshold, passed."""
    application = _bank_application(user, arguments)
    score = Score.objects.filter(application=application).first()
    if score is None:
        return {
            "application_id": application.pk,
            "score": None,
            "message": "Скоринга нет: заявка не дошла до оценки или остановлена стоп-фактором.",
        }
    card = _scorecard(score.model_version)
    reasons = _reasons(_decision(application))
    factors = []
    for factor in score.factors:
        reason = reasons.get(factor["name"], {})
        maximum = _max_points(card, factor["name"])
        factors.append(
            {
                "name": factor["name"],
                "value": factor["value"],
                "points": factor["points"],
                "max_points": maximum,
                "lost_points": None if maximum is None else maximum - int(factor["points"]),
                "threshold": reason.get("threshold"),
                "passed": reason.get("passed"),
                "message": factor["message"],
            }
        )
    factors.sort(key=lambda item: item["lost_points"] or 0, reverse=True)
    missing = [
        name
        for name in card.key_metrics
        if any(f["name"] == name and f["value"] is None for f in score.factors)
    ]
    plan = approval_plan(score.factors, score.model_version)
    return {
        "application_id": application.pk,
        "grade": score.grade,
        "total": score.total,
        "model_version": score.model_version,
        "grade_scale": [{"grade": grade, "min_total": minimum} for minimum, grade in card.grades],
        "grade_zone": GRADE_ZONES.get(score.grade),
        "factors": factors,
        "missing_key_metrics": missing,
        "approval_plan": None
        if plan is None
        else {
            "target_grade": plan.target_grade,
            "target_total": plan.target_total,
            "steps": [
                {
                    "metric": step.metric,
                    "current": money(step.current),
                    "target": money(step.target),
                    "points": step.points,
                    "message": step.message,
                }
                for step in plan.steps
            ],
        },
    }


def dscr_and_limits(user: AbstractBaseUser, arguments: dict) -> dict:
    """Debt capacity: DSCR now and with the new payment, the DSCR cap, the product limits."""
    application = _bank_application(user, arguments)
    product = application.product
    snapshot = latest_snapshot(application.company)
    reasons = _reasons(_decision(application))
    offer = current_offer(application)
    params = (product.params or {}) if product else {}
    current: dict | None = None
    leverage: dict | None = None
    if snapshot is not None:
        if snapshot.cfads is not None and snapshot.debt_service is not None:
            current = _metric(dscr(snapshot.cfads, snapshot.debt_service))
        if snapshot.debt is not None and snapshot.ebitda is not None:
            leverage = _metric(debt_to_ebitda(snapshot.debt, snapshot.ebitda, snapshot.cash or 0))
    return {
        "application_id": application.pk,
        "snapshot": None
        if snapshot is None
        else {
            "period": snapshot.period,
            "cleaned_credit_turnover": money(snapshot.cleaned_credit_turnover),
            "cfads": money(snapshot.cfads),
            "debt_service": money(snapshot.debt_service),
            "ebitda": money(snapshot.ebitda),
            "debt": money(snapshot.debt),
        },
        "dscr_now": current
        or {"value": None, "note": "Нет денежного потока или платежей по долгам в выписке."},
        "debt_to_ebitda": leverage
        or {"value": None, "note": "Нет отчётности: долговая нагрузка по EBITDA не считается."},
        "min_dscr": params.get("min_dscr", "1.25"),
        "max_debt_to_ebitda": None
        if product is None or product.is_revolving
        else params.get("max_debt_to_ebitda", "3.5"),
        "requested_amount": money(application.requested_amount),
        "offer_monthly_payment": None if offer is None else money(offer.monthly_payment),
        "limits": [reasons[name] for name in LIMIT_METRICS if name in reasons],
        "message": None
        if snapshot is not None
        else "Выписки по счёту нет: денежный поток и лимиты не посчитаны — это не негатив.",
    }


def policy_compare(user: AbstractBaseUser, arguments: dict) -> dict:
    """The application against the credit policy, row by row: requirements, thresholds, stops."""
    application = _bank_application(user, arguments)
    product = application.product
    company = application.company
    decision = _decision(application)
    reasons = _reasons(decision)
    policy = _policy(decision.policy_version if decision else None)
    rows: list[dict] = []

    def row(rule: str, value, threshold, passed: bool | None, message: str) -> None:
        rows.append(
            {"rule": rule, "value": value, "threshold": threshold, "passed": passed,
             "message": message}
        )  # fmt: skip

    if product is None:
        row("product", None, None, False, "Продукт не выбран — требования продукта не проверить")
    else:
        requirements = product.requirements or {}
        forms = requirements.get("legal_forms") or []
        if forms:
            row("legal_form", company.legal_form, forms, company.legal_form in forms,
                "Правовая форма из требований продукта")  # fmt: skip
        age, minimum = _age(application), int(requirements.get("min_business_age_months") or 0)
        row("business_age_months", age, minimum, None if age is None else age >= minimum,
            "Возраст бизнеса, месяцев, против минимума продукта")  # fmt: skip
        amount = application.requested_amount
        row("requested_amount", money(amount),
            [money(product.amount_min), money(product.amount_max)],
            product.amount_min <= amount <= product.amount_max,
            "Сумма в границах продукта")  # fmt: skip
        term = application.term_months
        row("term_months", term, [product.term_min_months, product.term_max_months],
            product.term_min_months <= term <= product.term_max_months,
            "Срок в границах продукта")  # fmt: skip
        if product.collateral_required:
            described = bool((application.collateral_description or "").strip())
            row("collateral", described, True, described, "Продукт требует залог")
        if product.kind == "factoring":
            row("invoice_amount", money(application.invoice_amount), None,
                application.invoice_amount is not None, "Сумма отгрузки по документу")  # fmt: skip
    for name in FACTORS:
        reason = reasons.get(name)
        if reason is not None:
            row(name, reason["value"], reason["threshold"], reason["passed"], reason["message"])
    stops = [
        {"code": STOP_METRICS[name], "message": reasons[name]["message"]}
        for name in STOP_METRICS
        if name in reasons and reasons[name]["passed"] is False and name != "business_age_months"
    ]
    if "business_age_months" in reasons and decision and decision.grade is None:
        age_reason = reasons["business_age_months"]
        if age_reason["passed"] is False:
            stops.append({"code": STOP_METRICS["business_age_months"],
                          "message": age_reason["message"]})  # fmt: skip
    no_data = [
        {"source": name.removeprefix("source_"), "message": reason["message"]}
        for name, reason in reasons.items()
        if name.startswith("source_")
    ]
    grade = decision.grade if decision else None
    return {
        "application_id": application.pk,
        "policy_version": policy.policy_version,
        "rows": rows,
        "stop_factors": stops,
        "no_data": no_data,
        "grade": grade,
        "grade_zone": GRADE_ZONES.get(grade) if grade else None,
        "max_missing_key_metrics": policy.max_missing_key_metrics,
        "message": None
        if decision
        else "Решения конвейера ещё нет: пороги скоринга появятся после проверки.",
        "note": "Нет данных по источнику — ручное рассмотрение или запрос документов, не отказ.",
    }


def missing_documents(user: AbstractBaseUser, arguments: dict) -> dict:
    """What to ask the client for: product documents not uploaded, open requests, empty fields,
    and documents that replace a source that said nothing (SRC3: ask, do not decline)."""
    application = _bank_application(user, arguments)
    product = application.product
    uploaded = set(application.documents.values_list("kind", flat=True))
    required = list(product.required_documents) if product else []
    by_sources = []
    for check in application.checks.all():
        status = check.status
        if check.source == "bank_account" and (check.data or {}).get("not_connected"):
            status = "unavailable"
        ask = ASK_FOR.get((check.source, status))
        if ask:
            by_sources.append(
                {"source": SOURCE_NAME.get(check.source, check.source), "status": status,
                 "ask": ask}
            )  # fmt: skip
    return {
        "application_id": application.pk,
        "missing_product_documents": _kinds([kind for kind in required if kind not in uploaded]),
        "uploaded": _kinds(sorted(uploaded)),
        "open_info_requests": [
            {"message": request.message, "document_kinds": _kinds(request.document_kinds)}
            for request in application.info_requests.filter(status=InfoRequestStatus.OPEN)
        ],
        "field_gaps": [
            {"field": field, "message": text} for field, text in field_gaps(application)
        ],
        "because_of_sources": by_sources,
        "note": "Скрытые или не полученные сведения — повод запросить документы, "
        "не причина отказа.",
    }


class DraftCommentSerializer(serializers.Serializer):
    application_id = serializers.IntegerField(min_value=1)
    preliminary_intent = serializers.ChoiceField(choices=sorted(INTENTS))


def draft_officer_comment(user: AbstractBaseUser, arguments: dict) -> dict:
    """A draft of the officer's comment under a PRELIMINARY intent, made of the stored facts.

    It is text only: nothing is saved, nothing changes — the officer edits it and decides in the
    card. The intent is the officer's preliminary leaning, not a decision, and the text says so.
    """
    data = validated(DraftCommentSerializer, arguments)
    application = _bank_application(user, {"application_id": data["application_id"]})
    intent = data["preliminary_intent"]
    decision = _decision(application)
    reasons = _reasons(decision)
    score = Score.objects.filter(application=application).first()
    failed = [
        r for name, r in reasons.items()
        if name in FACTORS and r["passed"] is False and r["value"] is not None
    ]  # fmt: skip
    no_data = [r for name, r in reasons.items() if name.startswith("source_")]
    stops = [
        reasons[name] for name in STOP_METRICS
        if name in reasons and reasons[name]["passed"] is False
        and (name != "business_age_months" or (decision and decision.grade is None))
    ]  # fmt: skip
    facts: list[str] = []
    if score is not None:
        facts.append(f"Грейд {score.grade} ({score.total} из 100).")
    facts.extend(f"{r['message']}." for r in stops)
    facts.extend(f"{r['message']}." for r in failed[:3])
    facts.extend(f"{r['message']}." for r in no_data)
    cap = reasons.get("max_loan_by_dscr")
    requested = application.requested_amount
    lines = [
        f"Предварительно склоняюсь {INTENTS[intent]} — это не решение, решение за сотрудником."
    ]
    if intent == "approve":
        lines.append(
            f"Запрошено {rubles(requested)} на {application.term_months} мес"
            + (f", {application.product.name.lower()}" if application.product else "")
            + "."
        )
    elif intent == "counteroffer":
        if cap and cap.get("value") is not None:
            lines.append(
                f"Денежный поток выдерживает до {rubles(Decimal(cap['value']))} "
                f"при запрошенных {rubles(requested)}."
            )
        else:
            lines.append("Сумму иных условий определить по денежному потоку клиента.")
    elif intent == "request_info":
        asks = missing_documents(user, {"application_id": application.pk})
        items = [doc["name"] for doc in asks["missing_product_documents"]]
        items += [item["ask"] for item in asks["because_of_sources"]]
        items += [gap["message"] for gap in asks["field_gaps"]]
        lines.append(
            "Запросить у клиента: " + "; ".join(dict.fromkeys(items)) + "."
            if items
            else "Уточнить у клиента данные, которых не хватает для решения."
        )
    elif intent == "decline" and decision is not None and decision.improvements:
        lines.append("Что клиент может улучшить: " + "; ".join(decision.improvements[:3]) + ".")
    if facts:
        lines.append("Основание: " + " ".join(facts))
    warnings: list[str] = []
    if intent == "decline" and not stops and not failed and no_data:
        warnings.append(
            "Отказ только из-за отсутствия данных противоречит правилу «нет данных не значит "
            "плохо» (SRC3): лучше запросить документы или проверить вручную."
        )
    if intent in {"approve", "counteroffer"} and stops:
        warnings.append("Есть стоп-фактор: при сильных показателях нужно решение риск-менеджера.")
    if score is not None and score.grade == "E" and intent == "approve":
        warnings.append("Грейд E: одобрение вне политики, нужно решение риск-менеджера.")
    return {
        "application_id": application.pk,
        "preliminary_intent": intent,
        "draft_comment": " ".join(lines),
        "warnings": warnings,
        "is_saved": False,
        "note": "Черновик ничего не сохраняет: текст вставляет и правит сотрудник.",
    }


# ───────────────────────── registry ─────────────────────────

TOOLS = registry(
    Tool(
        ToolSpec(
            "application_summary",
            "Общая картина по заявке: условия, компания, статус и срок реакции, решение "
            "конвейера, предложение, проверки, запросы и документы.",
            BANK_APPLICATION_ID,
        ),
        application_summary,
    ),
    Tool(
        ToolSpec(
            "checks_with_provenance",
            "Проверки источников (ЕГРЮЛ, «Прозрачный бизнес», БКИ, выписка): статус и что он "
            "значит для решения, данные, когда и откуда пришёл ответ.",
            BANK_APPLICATION_ID,
        ),
        checks_with_provenance,
    ),
    Tool(
        ToolSpec(
            "score_breakdown",
            "Скоринг: грейд, баллы, каждый фактор со значением, баллами из максимума, порогом "
            "и итогом, пропущенные ключевые метрики, план до грейда C.",
            BANK_APPLICATION_ID,
        ),
        score_breakdown,
    ),
    Tool(
        ToolSpec(
            "dscr_and_limits",
            "Платёжеспособность: DSCR сейчас и с новым платежом против порога, долг/EBITDA, "
            "максимум суммы по денежному потоку и лимиты продукта.",
            BANK_APPLICATION_ID,
        ),
        dscr_and_limits,
    ),
    Tool(
        ToolSpec(
            "policy_compare",
            "Заявка против кредитной политики построчно: требования продукта, пороги факторов, "
            "стоп-факторы, источники без данных, зона грейда.",
            BANK_APPLICATION_ID,
        ),
        policy_compare,
    ),
    Tool(
        ToolSpec(
            "missing_documents",
            "Что запросить у клиента: недостающие документы продукта, открытые запросы, "
            "незаполненные поля, документы вместо источников без данных.",
            BANK_APPLICATION_ID,
        ),
        missing_documents,
    ),
    Tool(
        ToolSpec(
            "draft_officer_comment",
            "Черновик комментария сотрудника по фактам заявки под ПРЕДВАРИТЕЛЬНОЕ намерение "
            "(approve, counteroffer, request_info, decline). Ничего не сохраняет и не меняет.",
            {
                "type": "object",
                "required": ["application_id", "preliminary_intent"],
                "additionalProperties": False,
                "properties": {
                    "application_id": {"type": "integer", "minimum": 1},
                    "preliminary_intent": {
                        "type": "string",
                        "enum": sorted(INTENTS),
                        "description": "Предварительное намерение сотрудника, не решение",
                    },
                },
            },
        ),
        draft_officer_comment,
    ),
)


def tool_specs() -> list[ToolSpec]:
    return [tool.spec for tool in TOOLS.values()]


def run_tool(user: AbstractBaseUser, name: str, arguments: Any) -> dict:
    """Run one bank tool as `user`. Errors come back as data for the model, never raised."""
    return run_registry(TOOLS, user, name, arguments)
