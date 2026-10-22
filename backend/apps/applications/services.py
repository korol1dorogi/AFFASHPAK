"""Use cases on top of the state machine (docs/state-machine.md).

Views and the pipeline (L4) call these functions; nothing else writes status, version,
decisions or offers. Each function is atomic and works on a locked application row.
"""

import secrets
from datetime import timedelta
from decimal import Decimal
from typing import Any

from django.contrib.auth.hashers import check_password, make_password
from django.contrib.auth.models import AbstractBaseUser
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import NotFound, ValidationError

from apps.applications.access import SYSTEM, Actor, current_membership
from apps.applications.models import (
    BKI_CONSENT_VERSION,
    Application,
    ApplicationStatus,
    BkiConsent,
    DecidedBy,
    Decision,
    DecisionOutcome,
    Disbursement,
    EventKind,
    InfoRequest,
    InfoRequestOrigin,
    InfoRequestStatus,
    OfferStatus,
    Signature,
)
from apps.applications.offers import create_offer, current_offer, rate_for
from apps.applications.transitions import (
    apply_transition,
    check_action,
    check_version,
    lock_application,
    record_event,
    touch,
)
from apps.products.models import Product
from apps.scoring.policy import CURRENT_POLICY_VERSION

S = ApplicationStatus
SIGNATURE_TTL = timedelta(minutes=10)
SIGNATURE_ATTEMPTS = 3  # D17

EDITABLE_FIELDS = (
    "need_type",
    "purpose",
    "requested_amount",
    "term_months",
    "invoice_amount",
    "collateral_description",
)


def _product(code: str | None) -> Product | None:
    if code is None:
        return None
    product = Product.objects.filter(code=code, is_active=True).first()
    if product is None:
        raise ValidationError({"product_code": ["Такого продукта нет в каталоге."]})
    return product


# ───────────────────────── client ─────────────────────────


def create_application(user: AbstractBaseUser, data: dict[str, Any]) -> Application:
    membership = current_membership(user)
    if membership is None:
        raise NotFound("Сначала добавьте компанию.")
    return Application.objects.create(
        company=membership.company,
        created_by=user,
        product=_product(data.get("product_code")),
        **{field: data[field] for field in EDITABLE_FIELDS if field in data},
        prefill_source=data.get("prefill_source", "manual"),
    )


def update_draft(application: Application, actor: Actor, data: dict[str, Any]) -> Application:
    with transaction.atomic():
        app = lock_application(application.pk)
        check_action(app, "edit", actor)
        touch(app, version=data["version"])
        changed = ["version"]
        for field in EDITABLE_FIELDS:
            if field in data:
                setattr(app, field, data[field])
                changed.append(field)
        if "product_code" in data:
            app.product = _product(data["product_code"])
            changed.append("product")
        app.save(update_fields=changed)
        return app


BKI_CONSENT_MESSAGE = "Согласие на запрос в БКИ"


def submit(application: Application, actor: Actor, *, consent_version: str) -> Application:
    """Consent to the credit bureau request goes with the submit, in the same transaction:
    an application in the bank always has it (218-FZ)."""
    if consent_version != BKI_CONSENT_VERSION:
        raise ValidationError(
            {"bki_consent": ["Текст согласия обновился. Обновите страницу и подтвердите снова."]}
        )
    with transaction.atomic():
        app = lock_application(application.pk)
        check_action(app, "submit", actor)
        BkiConsent.objects.update_or_create(
            application=app,
            defaults={"user": actor.user, "text_version": consent_version},
        )
        record_event(
            app,
            actor,
            EventKind.CONSENT_GIVEN,
            BKI_CONSENT_MESSAGE,
            payload={"text_version": consent_version},
        )
        apply_transition(
            app,
            "submit",
            actor,
            message="Заявка отправлена в банк.",
            notify=("Заявка отправлена", "Скоро начнём автоматическую проверку."),
        )
        return app


def cancel(application: Application, actor: Actor) -> Application:
    with transaction.atomic():
        app = lock_application(application.pk)
        apply_transition(app, "cancel", actor, message="Заявка отозвана клиентом.")
        app.offers.filter(status=OfferStatus.ACTIVE).update(status=OfferStatus.DECLINED)
        return app


def accept_offer(application: Application, actor: Actor) -> Application:
    with transaction.atomic():
        app = lock_application(application.pk)
        offer = app.offers.filter(status=OfferStatus.ACTIVE).first()
        check_action(app, "accept_offer", actor)
        if offer is None or offer.expires_at <= timezone.now():
            raise ValidationError({"offer": ["Предложение истекло. Обратитесь в банк."]})
        apply_transition(app, "accept_offer", actor, message="Предложение принято.")
        offer.status = OfferStatus.ACCEPTED
        offer.save(update_fields=["status"])
        return app


def decline_offer(application: Application, actor: Actor) -> Application:
    with transaction.atomic():
        app = lock_application(application.pk)
        apply_transition(app, "decline_offer", actor, message="Клиент отказался от предложения.")
        app.offers.filter(status=OfferStatus.ACTIVE).update(status=OfferStatus.DECLINED)
        return app


def start_signature(application: Application, actor: Actor) -> tuple[Signature, str]:
    """New 6-digit code shown on screen (no SMS, O5). Only its hash is stored."""
    with transaction.atomic():
        app = lock_application(application.pk)
        check_action(app, "sign", actor)
        code = f"{secrets.randbelow(10**6):06d}"
        signature, _ = Signature.objects.update_or_create(
            application=app,
            defaults={
                "code_hash": make_password(code),
                "expires_at": timezone.now() + SIGNATURE_TTL,
                "attempts_left": SIGNATURE_ATTEMPTS,
                "signed_at": None,
                "signed_by": None,
            },
        )
        return signature, code


def confirm_signature(application: Application, actor: Actor, code: str) -> Application:
    """A wrong code spends an attempt: the counter is committed, then 400 is raised."""
    with transaction.atomic():
        app = lock_application(application.pk)
        check_action(app, "confirm_signature", actor)
        signature = Signature.objects.select_for_update().filter(application=app).first()
        if signature is None or signature.expires_at <= timezone.now():
            raise ValidationError({"code": ["Код истёк. Получите новый код."]})
        if signature.attempts_left == 0:
            raise ValidationError({"code": ["Попытки закончились. Получите новый код."]})
        if check_password(code, signature.code_hash):
            signature.signed_at = timezone.now()
            signature.signed_by = actor.user
            signature.save(update_fields=["signed_at", "signed_by"])
            apply_transition(
                app,
                "confirm_signature",
                actor,
                event_kind=EventKind.SIGNED,
                message="Договор подписан кодом с экрана.",
                notify=("Договор подписан", "Деньги поступят на счёт после обработки выдачи."),
            )
            offer = current_offer(app)
            Disbursement.objects.update_or_create(
                application=app,
                defaults={"amount": offer.amount if offer else app.requested_amount},
            )
            application_id = app.pk

            def _disburse() -> None:
                from apps.pipeline.tasks import enqueue_disbursement

                enqueue_disbursement(application_id)

            transaction.on_commit(_disburse)
            return app
        signature.attempts_left -= 1
        signature.save(update_fields=["attempts_left"])
        attempts_left = signature.attempts_left
    raise ValidationError({"code": [f"Неверный код. Осталось попыток: {attempts_left}."]})


def respond_info(
    application: Application, actor: Actor, request_id: int, message: str
) -> Application:
    with transaction.atomic():
        app = lock_application(application.pk)
        info = (
            InfoRequest.objects.select_for_update()
            .filter(pk=request_id, application=app, status=InfoRequestStatus.OPEN)
            .first()
        )
        if info is None:
            raise NotFound("Запрос не найден или на него уже ответили.")
        target = S.SUBMITTED if info.origin == InfoRequestOrigin.VALIDATION else S.MANUAL_REVIEW
        apply_transition(
            app,
            "respond_info",
            actor,
            target=target,
            event_kind=EventKind.INFO_RESPONDED,
            message=message,
        )
        info.status = InfoRequestStatus.ANSWERED
        info.response_message = message
        info.answered_by = actor.user
        info.answered_at = timezone.now()
        info.save(update_fields=["status", "response_message", "answered_by", "answered_at"])
        if target == S.SUBMITTED:
            # state-machine.md 10a: the completeness check asked, the client answered —
            # the pipeline runs again (was: the application stayed «submitted» for good).
            application_id = app.pk

            def _rerun() -> None:
                from apps.pipeline.tasks import enqueue

                enqueue(application_id)

            transaction.on_commit(_rerun)
        return app


# ───────────────────────── bank ─────────────────────────


def assign(application: Application, actor: Actor, version: int) -> Application:
    with transaction.atomic():
        app = lock_application(application.pk)
        check_action(app, "assign", actor)
        touch(app, version=version)
        app.assignee = actor.user
        app.save(update_fields=["assignee"])
        record_event(
            app, actor, EventKind.ASSIGNED, "Заявку взял сотрудник банка.", is_internal=True
        )
        return app


def _officer_decision(app: Application, actor: Actor, outcome: str, **fields: Any) -> Decision:
    grade = getattr(getattr(app, "score", None), "grade", None)
    return Decision.objects.create(
        application=app,
        outcome=outcome,
        decided_by=DecidedBy.OFFICER,
        officer=actor.user,
        grade=grade,
        policy_version=CURRENT_POLICY_VERSION,  # the rules in force; decided_by says who
        **fields,
    )


def bank_approve(
    application: Application, actor: Actor, version: int, comment: str | None = None
) -> Application:
    with transaction.atomic():
        app = lock_application(application.pk)
        check_action(app, "approve", actor)
        check_version(app, version)  # stale screen → 409 before any validation
        if app.product is None:
            raise ValidationError(
                {"product_code": ["В заявке не выбран продукт — сделайте контрпредложение."]}
            )
        decision = _officer_decision(app, actor, DecisionOutcome.OFFER, comment=comment)
        create_offer(
            app,
            decision,
            product=app.product,
            amount=app.requested_amount,
            term_months=app.term_months,
            rate=rate_for(app.product, decision.grade),
        )
        apply_transition(
            app,
            "approve",
            actor,
            version=version,
            event_kind=EventKind.DECISION,
            message="Сотрудник банка одобрил заявку.",
            notify=("Готово предложение", "Банк одобрил заявку. Посмотрите условия."),
        )
        return app


def bank_counteroffer(
    application: Application,
    actor: Actor,
    *,
    version: int,
    amount: Decimal,
    term_months: int,
    rate: Decimal,
    comment: str,
    product_code: str | None = None,
) -> Application:
    with transaction.atomic():
        app = lock_application(application.pk)
        check_action(app, "counteroffer", actor)
        check_version(app, version)  # stale screen → 409 before any validation
        product = _product(product_code) or app.product
        if product is None:
            raise ValidationError({"product_code": ["Укажите продукт."]})
        changed = app.product_id is not None and product.pk != app.product_id
        outcome = DecisionOutcome.ALTERNATIVE_PRODUCT if changed else DecisionOutcome.COUNTEROFFER
        decision = _officer_decision(app, actor, outcome, comment=comment)
        create_offer(
            app, decision, product=product, amount=amount, term_months=term_months, rate=rate
        )
        apply_transition(
            app,
            "counteroffer",
            actor,
            version=version,
            event_kind=EventKind.DECISION,
            message=comment,
            notify=("Банк предлагает другие условия", comment),
        )
        return app


def bank_request_info(
    application: Application,
    actor: Actor,
    *,
    version: int,
    message: str,
    document_kinds: list[str] | None = None,
) -> Application:
    with transaction.atomic():
        app = lock_application(application.pk)
        check_action(app, "request_info", actor)
        check_version(app, version)  # stale screen → 409 before any validation
        _officer_decision(app, actor, DecisionOutcome.INFO_REQUESTED, comment=message)
        InfoRequest.objects.create(
            application=app,
            origin=InfoRequestOrigin.OFFICER,
            requested_by=actor.user,
            message=message,
            document_kinds=document_kinds or [],
        )
        apply_transition(
            app,
            "request_info",
            actor,
            version=version,
            event_kind=EventKind.INFO_REQUESTED,
            message=message,
            notify=("Банк просит уточнить данные", message),
        )
        return app


def bank_decline(
    application: Application,
    actor: Actor,
    *,
    version: int,
    reasons_text: str,
    improvements: list[str],
) -> Application:
    with transaction.atomic():
        app = lock_application(application.pk)
        check_action(app, "decline", actor)
        check_version(app, version)  # stale screen → 409 before any validation
        _officer_decision(
            app, actor, DecisionOutcome.DECLINED, comment=reasons_text, improvements=improvements
        )
        app.offers.filter(status=OfferStatus.ACTIVE).update(status=OfferStatus.DECLINED)
        apply_transition(
            app,
            "decline",
            actor,
            version=version,
            event_kind=EventKind.DECISION,
            message=reasons_text,
            notify=("Банк отказал", reasons_text),
        )
        return app


def bank_comment(application: Application, actor: Actor, message: str):
    if not actor.is_bank:
        raise NotFound("Не найдено.")
    return record_event(application, actor, EventKind.COMMENT, message, is_internal=True)


# ───────────────────────── system (pipeline, L4) ─────────────────────────


def start_processing(application_id: int) -> Application:
    with transaction.atomic():
        app = lock_application(application_id)
        apply_transition(
            app, "start_processing", SYSTEM, message="Началась автоматическая проверка."
        )
        return app


def record_auto_decision(
    application_id: int,
    *,
    outcome: str,
    grade: str | None,
    policy_version: str,
    reasons: list[dict],
    improvements: list[str] | None = None,
    offer: dict | None = None,
    info_request: dict | None = None,
    source_unavailable: bool = False,
) -> Application:
    """Store the pipeline's decision and move the application accordingly.

    offer: {"product": Product, "amount", "term_months", "rate"} for offer outcomes;
    info_request: {"message", "fields", "document_kinds"} for info_requested.
    """
    target = {
        DecisionOutcome.OFFER: S.OFFER,
        DecisionOutcome.COUNTEROFFER: S.OFFER,
        DecisionOutcome.ALTERNATIVE_PRODUCT: S.OFFER,
        DecisionOutcome.MANUAL_REVIEW: S.MANUAL_REVIEW,
        DecisionOutcome.INFO_REQUESTED: S.INFO_REQUESTED,
        DecisionOutcome.DECLINED: S.DECLINED,
    }[outcome]
    notify = {
        S.OFFER: ("Готово предложение", "Посмотрите условия и примите решение."),
        S.MANUAL_REVIEW: ("Заявку смотрит сотрудник банка", "Обычно это занимает до одного дня."),
        S.INFO_REQUESTED: ("Уточните данные", "Без этого мы не сможем продолжить проверку."),
        S.DECLINED: ("Банк отказал", "Посмотрите причины и что можно улучшить."),
    }[target]
    with transaction.atomic():
        app = lock_application(application_id)
        decision = Decision.objects.create(
            application=app,
            outcome=outcome,
            decided_by=DecidedBy.AUTO,
            grade=grade,
            policy_version=policy_version,
            reasons=reasons,
            improvements=improvements or [],
        )
        if offer is not None:
            create_offer(app, decision, reasons=reasons, **offer)
        if info_request is not None:
            InfoRequest.objects.create(
                application=app, origin=InfoRequestOrigin.VALIDATION, **info_request
            )
        if source_unavailable and not app.source_unavailable:
            app.source_unavailable = True
            app.save(update_fields=["source_unavailable"])
        apply_transition(
            app,
            "auto_decide",
            SYSTEM,
            target=target,
            event_kind=EventKind.DECISION,
            message=f"Предварительная оценка: {decision.get_outcome_display().lower()}.",
            notify=notify,
        )
        return app


def mark_issued(application_id: int, account_masked: str = "") -> Application:
    """Simulated disbursement finished (S1 simulator → pipeline)."""
    with transaction.atomic():
        app = lock_application(application_id)
        disbursement = Disbursement.objects.select_for_update().get(application=app)
        disbursement.status = "done"
        disbursement.issued_at = timezone.now()
        disbursement.account_masked = account_masked
        disbursement.save(update_fields=["status", "issued_at", "account_masked"])
        apply_transition(
            app,
            "disburse",
            SYSTEM,
            event_kind=EventKind.ISSUED,
            message="Деньги выданы.",
            notify=("Деньги выданы", f"Сумма {disbursement.amount} ₽ отправлена на счёт."),
        )
        return app
