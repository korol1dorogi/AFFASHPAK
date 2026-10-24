"""validation → enrichment (parallel) → scoring → decision.

Stops that are visible from the company alone (liquidation) decline before any source is called.
"""

import json
import logging
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from apps.applications.access import SYSTEM
from apps.applications.completeness import field_gaps
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
from apps.documents.models import DocumentKind
from apps.integrations.adapters import fetch_all
from apps.pipeline.decide import SOURCE_NAME, decide
from apps.scoring import CURRENT_POLICY_VERSION, build_input
from apps.scoring.texts import points

S = ApplicationStatus
logger = logging.getLogger(__name__)

NO_CONSENT_TEXT = "не запрашивали: клиент не дал согласия"
CHECK_TEXT = {
    "ok": "данные получены",
    "warning": "есть замечания",
    "failed": "проверка не пройдена",
    "unavailable": "источник не ответил, проверит сотрудник банка",
    "not_found": "компания не найдена в реестре",
    "restricted": "сведения скрыты, проверит сотрудник банка",
    "consent_missing": NO_CONSENT_TEXT,
}
PIPELINE_FAILED = (
    "Автоматическая проверка не завершилась, поэтому заявку проверит сотрудник банка. Это не отказ"
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
    # Stop factors come before completeness (decision-model.md §2): a liquidated company is
    # declined, not asked for documents it could never use.
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
            f"Оценка риска {outcome.score.grade}: {points(outcome.score.total)} из 100.",
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
                **(answer.get("provenance") or {}),
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
    """Fields are checked on submit (completeness.py); here they are only a safety net, so in
    practice the pipeline asks for documents — the one thing the client can add after sending."""
    gaps = field_gaps(application)
    fields = [field for field, _message in gaps]
    messages = [message for _field, message in gaps]
    documents: list[str] = []
    product = application.product
    if product is not None:
        present = set(application.documents.values_list("kind", flat=True))
        documents = [kind for kind in product.required_documents if kind not in present]
        if documents:
            # «Документ отгрузки (УПД)» → «документ отгрузки (УПД)»: only the first letter goes down
            labels = (str(DocumentKind(kind).label) for kind in documents)
            names = ", ".join(label[:1].lower() + label[1:] for label in labels)
            messages.append(f"Не хватает документов: {names}")
    if not fields and not documents:
        return None
    return {"message": ". ".join(messages), "fields": fields, "document_kinds": documents}


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
