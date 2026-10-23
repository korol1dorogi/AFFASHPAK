"""The application state machine (docs/state-machine.md). The only writer of status/version.

Every change goes through `apply_transition` on a row locked with `lock_application`:
it checks the source status, who is acting and the client's `version`, then moves the
status, bumps the version, writes the audit event and notifies the company.
"""

from dataclasses import dataclass

from django.db import transaction
from django.utils import timezone
from rest_framework import status
from rest_framework.exceptions import APIException, PermissionDenied

from apps.applications.access import Actor
from apps.applications.models import (
    ActorKind,
    Application,
    ApplicationEvent,
    ApplicationStatus,
    EventKind,
)

S = ApplicationStatus


class InvalidTransition(APIException):
    status_code = status.HTTP_409_CONFLICT
    default_detail = "Это действие недоступно для заявки в текущем статусе."
    default_code = "invalid_transition"


class VersionConflict(APIException):
    status_code = status.HTTP_409_CONFLICT
    default_detail = "Заявку уже изменили. Обновите страницу."
    default_code = "version_conflict"


# Who may perform an action: a client signatory or preparer, any client member, a bank user or
# the system.
SIGNATORY = "signatory"
PREPARER = "preparer"
CLIENT = "client"
BANK = "bank"
SYSTEM = "system"


@dataclass(frozen=True)
class Transition:
    sources: frozenset[str]
    targets: frozenset[str]
    who: str


def _t(sources: set[str], targets: set[str], who: str) -> Transition:
    return Transition(frozenset(sources), frozenset(targets), who)


TRANSITIONS: dict[str, Transition] = {
    "submit": _t({S.DRAFT}, {S.SUBMITTED}, SIGNATORY),
    "start_processing": _t({S.SUBMITTED}, {S.PROCESSING}, SYSTEM),
    "auto_decide": _t(
        {S.PROCESSING}, {S.OFFER, S.MANUAL_REVIEW, S.INFO_REQUESTED, S.DECLINED}, SYSTEM
    ),
    "approve": _t({S.MANUAL_REVIEW}, {S.OFFER}, BANK),
    "counteroffer": _t({S.MANUAL_REVIEW}, {S.OFFER}, BANK),
    "request_info": _t({S.MANUAL_REVIEW}, {S.INFO_REQUESTED}, BANK),
    "decline": _t({S.MANUAL_REVIEW}, {S.DECLINED}, BANK),
    "respond_info": _t({S.INFO_REQUESTED}, {S.SUBMITTED, S.MANUAL_REVIEW}, CLIENT),
    "accept_offer": _t({S.OFFER}, {S.SIGNING}, SIGNATORY),
    "decline_offer": _t({S.OFFER}, {S.CANCELLED}, SIGNATORY),
    "confirm_signature": _t({S.SIGNING}, {S.SIGNED}, SIGNATORY),
    "disburse": _t({S.SIGNED}, {S.ISSUED}, SYSTEM),
    # Up to the signature the client may walk away, signing included (fix 3.2).
    "cancel": _t(
        {S.DRAFT, S.SUBMITTED, S.MANUAL_REVIEW, S.INFO_REQUESTED, S.OFFER, S.SIGNING},
        {S.CANCELLED},
        SIGNATORY,
    ),
}

# Actions that do not change the status but still depend on it (available_actions).
NON_TRANSITION_ACTIONS: dict[str, Transition] = {
    "edit": _t({S.DRAFT}, set(), CLIENT),
    "upload_document": _t({S.DRAFT, S.INFO_REQUESTED}, set(), CLIENT),
    "sign": _t({S.SIGNING}, set(), SIGNATORY),
    # XP5: a preparer cannot send — they hand the ready draft to the signatories.
    "hand_off": _t({S.DRAFT}, set(), PREPARER),
    "assign": _t({S.SUBMITTED, S.PROCESSING, S.MANUAL_REVIEW, S.INFO_REQUESTED}, set(), BANK),
}

# Order of buttons in the UI; names match ApplicationAction in docs/openapi.yaml.
UI_ACTIONS: tuple[str, ...] = (
    "edit",
    "upload_document",
    "submit",
    "hand_off",
    "respond_info",
    "accept_offer",
    "decline_offer",
    "sign",
    "cancel",
    "assign",
    "approve",
    "counteroffer",
    "request_info",
    "decline",
)


def allowed(who: str, actor: Actor) -> bool:
    if who == SIGNATORY:
        return actor.is_signatory
    if who == PREPARER:
        return actor.is_preparer
    if who == CLIENT:
        return actor.is_client
    if who == BANK:
        return actor.is_bank
    return actor.is_system


def available_actions(application: Application, actor: Actor) -> list[str]:
    """What this actor can do right now; the frontend draws buttons only from this list."""
    result = []
    for name in UI_ACTIONS:
        rule = TRANSITIONS.get(name) or NON_TRANSITION_ACTIONS[name]
        if application.status in rule.sources and allowed(rule.who, actor):
            if name == "accept_offer" and _offer_expired(application):
                continue  # an expired offer is shown, but can no longer be accepted
            result.append(name)
    return result


def _offer_expired(application: Application) -> bool:
    from apps.applications.models import OfferStatus

    return application.offers.filter(
        status=OfferStatus.ACTIVE, expires_at__lte=timezone.now()
    ).exists()


def lock_application(application_id: int) -> Application:
    """Row lock for the rest of the current transaction (call inside transaction.atomic)."""
    if not transaction.get_connection().in_atomic_block:
        raise RuntimeError("lock_application must be called inside transaction.atomic()")
    return Application.objects.select_for_update().get(pk=application_id)


def check_version(application: Application, version: int | None) -> None:
    if version is not None and version != application.version:
        raise VersionConflict()


def check_action(application: Application, action: str, actor: Actor) -> Transition:
    rule = TRANSITIONS.get(action) or NON_TRANSITION_ACTIONS[action]
    if not allowed(rule.who, actor):
        raise PermissionDenied("Недостаточно прав для этого действия.")
    if application.status not in rule.sources:
        raise InvalidTransition()
    return rule


def touch(application: Application, *, version: int | None = None) -> None:
    """Non-status change (edit, assign): version check and bump, no status move."""
    check_version(application, version)
    application.version += 1
    application.save(update_fields=["version"])


def apply_transition(
    application: Application,
    action: str,
    actor: Actor,
    *,
    target: str | None = None,
    version: int | None = None,
    message: str = "",
    event_kind: str = EventKind.STATUS_CHANGED,
    payload: dict | None = None,
    notify: tuple[str, str] | None = None,
) -> ApplicationEvent:
    """Move a locked application along one transition. Returns the audit event."""
    from apps.notifications.services import notify_company

    rule = check_action(application, action, actor)
    check_version(application, version)
    if target is None:
        if len(rule.targets) != 1:
            raise ValueError(f"{action}: target is required, one of {sorted(rule.targets)}")
        (target,) = rule.targets
    elif target not in rule.targets:
        raise ValueError(f"{action}: {target} is not a valid target")

    now = timezone.now()
    from_status = application.status
    application.status = target
    application.version += 1
    application.status_changed_at = now
    fields = ["status", "version", "status_changed_at"]
    if target == S.SUBMITTED and application.submitted_at is None:
        application.submitted_at = now
        fields.append("submitted_at")
    if target in {S.OFFER, S.DECLINED} and application.decided_at is None:
        application.decided_at = now
        fields.append("decided_at")
    application.save(update_fields=fields)

    event = ApplicationEvent.objects.create(
        application=application,
        kind=event_kind,
        from_status=from_status,
        to_status=target,
        actor_kind=actor.kind if actor.kind in ActorKind.values else ActorKind.SYSTEM,
        actor=actor.user,
        message=message,
        payload=payload or {},
    )
    if notify is not None:
        title, text = notify
        notify_company(application, kind=event_kind, title=title, message=text, exclude=actor.user)
    return event


def record_event(
    application: Application,
    actor: Actor,
    kind: str,
    message: str = "",
    *,
    is_internal: bool = False,
    payload: dict | None = None,
) -> ApplicationEvent:
    """Audit event without a status change (document uploaded, assigned, comment…)."""
    return ApplicationEvent.objects.create(
        application=application,
        kind=kind,
        actor_kind=actor.kind,
        actor=actor.user,
        message=message,
        is_internal=is_internal,
        payload=payload or {},
    )
