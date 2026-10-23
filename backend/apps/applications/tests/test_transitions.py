"""State machine: every action × every status × every role (docs/state-machine.md)."""

import pytest
from django.db import transaction
from rest_framework.exceptions import PermissionDenied

from apps.accounts.models import UserKind
from apps.applications.access import SYSTEM, Actor
from apps.applications.models import ActorKind, ApplicationEvent, ApplicationStatus
from apps.applications.transitions import (
    NON_TRANSITION_ACTIONS,
    TRANSITIONS,
    InvalidTransition,
    VersionConflict,
    apply_transition,
    available_actions,
    check_action,
    lock_application,
)
from apps.core.factories import make_application, make_company, make_user
from apps.notifications.models import Notification

S = ApplicationStatus
ALL_STATUSES = sorted(S.values)

# The table from docs/state-machine.md, written out independently of transitions.py.
EXPECTED_SOURCES = {
    "submit": {S.DRAFT},
    "start_processing": {S.SUBMITTED},
    "auto_decide": {S.PROCESSING},
    "approve": {S.MANUAL_REVIEW},
    "counteroffer": {S.MANUAL_REVIEW},
    "request_info": {S.MANUAL_REVIEW},
    "decline": {S.MANUAL_REVIEW},
    "respond_info": {S.INFO_REQUESTED},
    "accept_offer": {S.OFFER},
    "decline_offer": {S.OFFER},
    "confirm_signature": {S.SIGNING},
    "disburse": {S.SIGNED},
    "cancel": {S.DRAFT, S.SUBMITTED, S.MANUAL_REVIEW, S.INFO_REQUESTED, S.OFFER, S.SIGNING},
}
EXPECTED_WHO = {
    "submit": "signatory",
    "start_processing": "system",
    "auto_decide": "system",
    "approve": "bank",
    "counteroffer": "bank",
    "request_info": "bank",
    "decline": "bank",
    "respond_info": "client",
    "accept_offer": "signatory",
    "decline_offer": "signatory",
    "confirm_signature": "signatory",
    "disburse": "system",
    "cancel": "signatory",
}


@pytest.fixture
def people(db):
    signatory = make_user("signatory")
    preparer = make_user("preparer")
    bank = make_user("bank", kind=UserKind.BANK)
    company = make_company(members={signatory: "signatory", preparer: "preparer"})
    return {
        "company": company,
        "signatory": Actor(kind=ActorKind.CLIENT, user=signatory, role="signatory"),
        "preparer": Actor(kind=ActorKind.CLIENT, user=preparer, role="preparer"),
        "bank": Actor(kind=ActorKind.BANK, user=bank),
        "system": SYSTEM,
    }


def actor_for_who(people: dict, who: str) -> Actor:
    return people["signatory" if who in {"signatory", "client"} else who]


def test_table_matches_the_documented_state_machine():
    assert set(TRANSITIONS) == set(EXPECTED_SOURCES)
    for action, rule in TRANSITIONS.items():
        assert rule.sources == EXPECTED_SOURCES[action], action
        assert rule.who == EXPECTED_WHO[action], action


@pytest.mark.django_db
@pytest.mark.parametrize("action", sorted(TRANSITIONS))
@pytest.mark.parametrize("status", ALL_STATUSES)
def test_action_is_allowed_only_from_its_source_statuses(people, action, status):
    application = make_application(people["company"], status=status)
    actor = actor_for_who(people, TRANSITIONS[action].who)

    if status in EXPECTED_SOURCES[action]:
        check_action(application, action, actor)
    else:
        with pytest.raises(InvalidTransition) as error:
            check_action(application, action, actor)
        assert error.value.status_code == 409
        assert error.value.get_codes() == "invalid_transition"


@pytest.mark.django_db
@pytest.mark.parametrize("action", sorted(TRANSITIONS))
@pytest.mark.parametrize("role", ["signatory", "preparer", "bank", "system"])
def test_only_the_right_role_may_act(people, action, role):
    rule = TRANSITIONS[action]
    (status,) = sorted(rule.sources)[:1]
    application = make_application(people["company"], status=status)
    allowed = {
        "signatory": {"signatory"},
        "client": {"signatory", "preparer"},
        "bank": {"bank"},
        "system": {"system"},
    }[rule.who]

    if role in allowed:
        check_action(application, action, people[role])
    else:
        with pytest.raises(PermissionDenied):
            check_action(application, action, people[role])


@pytest.mark.django_db
def test_transition_moves_status_bumps_version_writes_event_and_notifies(people):
    application = make_application(people["company"])
    with transaction.atomic():
        locked = lock_application(application.pk)
        apply_transition(
            locked, "submit", people["signatory"], version=0, notify=("Отправлено", "")
        )

    application.refresh_from_db()
    assert application.status == S.SUBMITTED
    assert application.version == 1
    assert application.submitted_at is not None
    event = ApplicationEvent.objects.get(application=application)
    assert (event.from_status, event.to_status) == (S.DRAFT, S.SUBMITTED)
    assert event.actor == people["signatory"].user
    # the preparer is notified, the signatory who acted is not
    assert list(Notification.objects.values_list("user__username", flat=True)) == ["preparer"]


@pytest.mark.django_db
def test_stale_version_is_409_and_changes_nothing(people):
    application = make_application(people["company"])
    with pytest.raises(VersionConflict) as error, transaction.atomic():
        locked = lock_application(application.pk)
        apply_transition(locked, "submit", people["signatory"], version=5)

    assert error.value.get_codes() == "version_conflict"
    application.refresh_from_db()
    assert (application.status, application.version) == (S.DRAFT, 0)
    assert not ApplicationEvent.objects.exists()


@pytest.mark.django_db
def test_target_must_be_one_of_the_allowed_targets(people):
    application = make_application(people["company"], status=S.PROCESSING)
    with pytest.raises(ValueError), transaction.atomic():
        apply_transition(lock_application(application.pk), "auto_decide", SYSTEM, target=S.ISSUED)


def test_lock_outside_a_transaction_is_a_programming_error():
    with pytest.raises(RuntimeError):
        lock_application(1)


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("status", "role", "expected"),
    [
        (S.DRAFT, "signatory", ["edit", "upload_document", "submit", "cancel"]),
        (S.DRAFT, "preparer", ["edit", "upload_document", "hand_off"]),  # XP5
        (S.DRAFT, "bank", []),
        (S.INFO_REQUESTED, "preparer", ["upload_document", "respond_info"]),
        (S.OFFER, "signatory", ["accept_offer", "decline_offer", "cancel"]),
        (S.OFFER, "preparer", []),
        (S.SIGNING, "signatory", ["sign", "cancel"]),  # fix 3.2: walk away before signing
        (S.MANUAL_REVIEW, "bank", ["assign", "approve", "counteroffer", "request_info", "decline"]),
        (S.MANUAL_REVIEW, "signatory", ["cancel"]),
        (S.ISSUED, "signatory", []),
        (S.DECLINED, "bank", []),
    ],
)
def test_available_actions(people, status, role, expected):
    application = make_application(people["company"], status=status)
    assert available_actions(application, people[role]) == expected


def test_every_ui_action_has_a_rule():
    from apps.applications.transitions import UI_ACTIONS

    for name in UI_ACTIONS:
        assert name in TRANSITIONS or name in NON_TRANSITION_ACTIONS
