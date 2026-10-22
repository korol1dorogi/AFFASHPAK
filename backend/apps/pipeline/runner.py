"""validation → enrichment (parallel) → scoring → decision.

Stops that are visible from the company alone (liquidation) decline before any source is called.
"""

import json
import logging
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from apps.applications.access import SYSTEM
from apps.applications.models import (
    Application,
    ApplicationStatus,
    BkiConsent,
    Check,
    DecisionOutcome,
    EventKind,
    Score,
)
from apps.applications.services import record_auto_decision, start_processing
from apps.applications.transitions import record_event
from apps.integrations.adapters import fetch_all
from apps.pipeline.decide import SOURCE_NAME, decide
from apps.scoring import CURRENT_POLICY_VERSION, build_input
from apps.scoring.texts import rubles

S = ApplicationStatus
logger = logging.getLogger(__name__)

NO_CONSENT_TEXT = "не запрашивали — нет согласия клиента"
CHECK_TEXT = {
    "ok": "данные получены",
    "warning": "есть замечания",
    "failed": "проверка не пройдена",
    "unavailable": "источник не ответил — проверит сотрудник",
    "not_found": "компания не найдена в реестре",
    "restricted": "сведения скрыты — проверит сотрудник",
    "consent_missing": NO_CONSENT_TEXT,
}
PIPELINE_FAILED = (
    "Автоматическая проверка не завершилась — заявку проверит сотрудник банка. Это не отказ"
)


def execute(application_id: int) -> None:
    """Never leaves an application in «processing»: on any error it goes to an officer."""
    application = Application.objects.select_related("company", "product").get(pk=application_id)
    if application.status != S.SUBMITTED:
        return
    start_processing(application.pk)
    application.refresh_from_db()
    try:
        _run(application)
    except Exception:
        logger.exception("pipeline failed for application %s", application_id)
        to_officer(application_id)


def to_officer(application_id: int) -> None:
    if Application.objects.filter(pk=application_id, status=S.PROCESSING).exists():
        record_auto_decision(
            application_id,
            outcome=DecisionOutcome.MANUAL_REVIEW,
            grade=None,
            policy_version=CURRENT_POLICY_VERSION,
            reasons=[
                {
                    "metric": "automatic_check",
                    "value": None,
                    "threshold": None,
                    "passed": False,
                    "message": PIPELINE_FAILED,
                }
            ],
        )


def _run(application: Application) -> None:
    gaps = _gaps(application)
    if gaps is not None:
        record_auto_decision(
            application.pk,
            outcome=DecisionOutcome.INFO_REQUESTED,
            grade=None,
            policy_version=CURRENT_POLICY_VERSION,
            reasons=[],
            info_request=gaps,
        )
        return

    company = application.company
    snapshot = company.snapshots.order_by("-period", "-id").first()
    early = build_input(
        _company_dict(company),
        _snapshot_dict(snapshot),
        {},
        on_date=_on_date(application),
    )
    from apps.scoring import stop_factors

    early_stops = stop_factors(early)
    if early_stops:
        _decline(application.pk, early_stops)
        return

    answers = fetch_all(
        company.inn,
        has_account=snapshot is not None,
        bki_consent=BkiConsent.objects.filter(application=application).exists(),
    )
    _store_checks(application, answers)
    checks = {
        source: {"status": answer["status"], "data": answer["data"]}
        for source, answer in answers.items()
    }
    scoring_input = build_input(
        _company_dict(company), _snapshot_dict(snapshot), checks, on_date=_on_date(application)
    )
    stops = stop_factors(scoring_input)
    if stops:
        _decline(application.pk, stops)
        return

    outcome = decide(application, scoring_input)
    if outcome.score is not None:
        Score.objects.update_or_create(
            application=application,
            defaults={
                "grade": outcome.score.grade,
                "total": outcome.score.total,
                "factors": outcome.score.factors_payload(),
                "model_version": outcome.score.model_version,
            },
        )
        record_event(
            application,
            SYSTEM,
            EventKind.SCORE_CALCULATED,
            f"Грейд {outcome.score.grade}, {outcome.score.total} баллов.",
        )
    record_auto_decision(
        application.pk,
        outcome=outcome.outcome,
        grade=None if outcome.score is None else outcome.score.grade,
        policy_version=outcome.policy_version,
        reasons=outcome.reasons,
        improvements=outcome.improvements,
        offer=outcome.offer,
        source_unavailable=outcome.source_unavailable,
    )


def _decline(application_id: int, stops) -> None:
    record_auto_decision(
        application_id,
        outcome=DecisionOutcome.DECLINED,
        grade=None,
        policy_version=CURRENT_POLICY_VERSION,
        reasons=[_reason(stop.reason) for stop in stops],
        improvements=[stop.improvement for stop in stops if stop.improvement],
    )


def _store_checks(application: Application, answers: dict[str, dict]) -> None:
    with transaction.atomic():
        for source, answer in answers.items():
            data = json.loads(json.dumps(answer["data"], default=str))
            Check.objects.create(
                application=application,
                source=source,
                status=answer["status"],
                summary=_summary(source, answer),
                data=data,
            )
            record_event(
                application,
                SYSTEM,
                EventKind.CHECK_COMPLETED,
                _summary(source, answer),
                payload={"source": source, "status": answer["status"]},
            )


def _summary(source: str, answer: dict) -> str:
    """«БКИ: данные получены» — what the client reads in the history, never a source code."""
    status = answer["status"]
    return f"{SOURCE_NAME[source]}: {CHECK_TEXT.get(status, status)}"


def _on_date(application: Application):
    moment = application.submitted_at or timezone.now()
    return timezone.localdate(moment)


def _company_dict(company) -> dict:
    return {
        "legal_form": company.legal_form,
        "registry_status": company.registry_status,
        "registered_at": company.registered_at,
    }


def _snapshot_dict(snapshot) -> dict | None:
    if snapshot is None:
        return None
    names = (
        "cleaned_credit_turnover",
        "cfads",
        "debt_service",
        "revenue",
        "cogs",
        "ebitda",
        "debt",
        "cash",
        "receivables",
        "inventory",
        "payables",
        "counterparty_concentration",
        "revenue_trend",
    )
    return {name: getattr(snapshot, name) for name in names}


def _gaps(application: Application) -> dict | None:
    from apps.scoring.policy import get_policy

    policy = get_policy()
    fields: list[str] = []
    documents: list[str] = []
    messages: list[str] = []
    product = application.product
    if len((application.purpose or "").strip()) < policy.purpose_min_length:
        fields.append("purpose")
        messages.append("Опишите цель подробнее: на что именно пойдут деньги")
    if product is None:
        fields.append("product_code")
        messages.append("Выберите продукт или воспользуйтесь подбором")
    else:
        if application.requested_amount < product.amount_min:
            fields.append("requested_amount")
            messages.append(f"Минимальная сумма по продукту — {rubles(product.amount_min)}")
        if not product.term_min_months <= application.term_months <= product.term_max_months:
            fields.append("term_months")
            messages.append(
                f"Срок по продукту — от {product.term_min_months} до {product.term_max_months} мес"
            )
        if product.kind == "factoring" and application.invoice_amount is None:
            fields.append("invoice_amount")
            messages.append("Укажите сумму отгрузки по документу")
        present = set(application.documents.values_list("kind", flat=True))
        missing = [kind for kind in product.required_documents if kind not in present]
        if missing:
            documents.extend(missing)
            messages.append("Загрузите недостающие документы")
    if not fields and not documents:
        return None
    return {"message": " ".join(messages), "fields": fields, "document_kinds": documents}


def _reason(reason) -> dict:
    def dump(value: Decimal | None) -> str | None:
        return None if value is None else format(value, "f")

    return {
        "metric": reason.metric,
        "value": dump(reason.value),
        "threshold": dump(reason.threshold),
        "passed": reason.passed,
        "message": reason.message,
    }
