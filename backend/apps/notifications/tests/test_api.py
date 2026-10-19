import pytest
from rest_framework.test import APIClient

from apps.core.factories import make_application, make_company, make_user
from apps.core.testing import assert_matches_contract
from apps.notifications.models import Notification


@pytest.fixture
def setup(db):
    me = make_user("me")
    other = make_user("other")
    application = make_application(make_company(members={me: "signatory"}))
    for title in ("Первое", "Второе", "Третье"):
        Notification.objects.create(user=me, application=application, kind="decision", title=title)
    foreign = Notification.objects.create(user=other, kind="decision", title="Чужое")
    client = APIClient()
    client.force_login(me)
    return client, foreign


def test_list_pagination_and_unread_count(setup):
    client, _ = setup
    response = client.get("/api/notifications", {"page_size": 2})

    assert response.status_code == 200
    assert_matches_contract(response, method="get", path="/api/notifications")
    body = response.json()
    assert body["count"] == 3
    assert body["unread_count"] == 3
    assert [item["title"] for item in body["results"]] == ["Третье", "Второе"]


def test_read_one_read_all_and_unread_filter(setup):
    client, _ = setup
    first = client.get("/api/notifications").json()["results"][0]

    assert client.post(f"/api/notifications/{first['id']}/read").status_code == 204
    assert client.get("/api/notifications", {"unread": "true"}).json()["count"] == 2

    assert client.post("/api/notifications/read-all").status_code == 204
    assert client.get("/api/notifications").json()["unread_count"] == 0


def test_someone_elses_notification_is_404(setup):
    client, foreign = setup
    assert client.post(f"/api/notifications/{foreign.pk}/read").status_code == 404
    foreign.refresh_from_db()
    assert foreign.read_at is None
