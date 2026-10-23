"""XP5: the preparer hands the ready draft to the signatories, who alone may send it."""

import pytest

from apps.applications.access import Actor
from apps.applications.models import ActorKind, ApplicationStatus
from apps.applications.transitions import available_actions
from apps.business.models import Membership
from apps.core.factories import make_application, make_user
from apps.core.testing import assert_matches_contract
from apps.notifications.models import Notification

pytestmark = pytest.mark.django_db
S = ApplicationStatus


def hand_off(client, pk: int):
    return client.post(f"/api/applications/{pk}/hand-off")


def path(pk: int) -> str:
    return f"/api/applications/{pk}/hand-off"


def test_the_preparer_hands_off_and_every_signatory_is_notified(world):
    second_signatory = make_user("owner", full_name="Борис Демо")
    second_preparer = make_user("finance", full_name="Вера Демо")
    Membership.objects.create(company=world["company"], user=second_signatory, role="signatory")
    Membership.objects.create(company=world["company"], user=second_preparer, role="preparer")
    application = make_application(world["company"])

    response = hand_off(world["as_preparer"], application.pk)

    assert response.status_code == 200
    assert_matches_contract(response, method="post", path=path(application.pk))
    body = response.json()
    assert body["status"] == S.DRAFT  # no status change
    assert body["version"] == application.version  # nothing in the draft changed
    assert "hand_off" in body["available_actions"]  # a reminder is allowed
    notified = set(Notification.objects.filter(kind="handed_off").values_list("user", flat=True))
    assert notified == {world["signatory"].pk, second_signatory.pk}  # not the preparers
    note = Notification.objects.filter(user=world["signatory"]).get()
    assert note.title == f"Заявка № {application.pk} готова к отправке"
    assert note.application_id == application.pk


def test_the_hand_off_is_in_the_client_timeline_with_who_did_it(world):
    application = make_application(world["company"])
    hand_off(world["as_preparer"], application.pk)

    events = world["as_signatory"].get(f"/api/applications/{application.pk}/events").json()
    handed = [event for event in events if event["kind"] == "handed_off"]
    assert len(handed) == 1
    assert handed[0]["message"] == "Заявка передана подписанту на отправку."
    assert handed[0]["actor"]["full_name"] == "Ольга Демо"
    assert handed[0]["is_internal"] is False


def test_a_second_hand_off_is_a_reminder(world):
    application = make_application(world["company"])
    hand_off(world["as_preparer"], application.pk)
    assert hand_off(world["as_preparer"], application.pk).status_code == 200
    assert Notification.objects.filter(user=world["signatory"], kind="handed_off").count() == 2


def test_an_unfinished_draft_is_400_by_field_and_nobody_is_notified(world):
    application = make_application(world["company"], product=None, purpose="Деньги")
    response = hand_off(world["as_preparer"], application.pk)
    assert response.status_code == 400
    assert_matches_contract(response, method="post", path=path(application.pk))
    assert set(response.json()["error"]["details"]) == {"product_code", "purpose"}
    assert not Notification.objects.exists()
    assert not application.events.filter(kind="handed_off").exists()


def test_the_signatory_does_not_hand_off_they_send(world):
    application = make_application(world["company"])
    response = hand_off(world["as_signatory"], application.pk)
    assert response.status_code == 403
    assert_matches_contract(response, method="post", path=path(application.pk))


def test_only_a_draft_can_be_handed_off(world):
    application = make_application(world["company"], status=S.SUBMITTED)
    response = hand_off(world["as_preparer"], application.pk)
    assert response.status_code == 409
    assert_matches_contract(response, method="post", path=path(application.pk))


def test_another_company_and_the_bank_get_404(world):
    application = make_application(world["company"])
    assert hand_off(world["as_outsider"], application.pk).status_code == 404
    assert hand_off(world["as_bank"], application.pk).status_code == 404


def test_hand_off_is_offered_to_the_preparer_in_a_draft_only(world):
    draft = make_application(world["company"])
    sent = make_application(world["company"], status=S.SUBMITTED)
    preparer = Actor(kind=ActorKind.CLIENT, user=world["preparer"], role="preparer")
    signatory = Actor(kind=ActorKind.CLIENT, user=world["signatory"], role="signatory")
    assert "hand_off" in available_actions(draft, preparer)
    assert "submit" not in available_actions(draft, preparer)
    assert "hand_off" not in available_actions(draft, signatory)
    assert "hand_off" not in available_actions(sent, preparer)
