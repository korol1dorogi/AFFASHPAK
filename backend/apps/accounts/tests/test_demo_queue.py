"""A fresh stand has a living bank queue: population applications decided by the real pipeline."""

from collections import Counter

import pytest
from django.core.management import call_command
from rest_framework.test import APIClient

from apps.accounts.demo import persona_catalog, seed
from apps.accounts.demo_queue import QUEUE_MARK, seed_queue
from apps.applications.models import Application

pytestmark = pytest.mark.django_db


@pytest.fixture
def media(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path


def test_the_queue_has_every_kind_of_outcome(media, django_capture_on_commit_callbacks):
    seed()
    with django_capture_on_commit_callbacks(execute=True):  # disbursement runs on commit
        assert seed_queue(30) == 30
    statuses = Counter(Application.objects.values_list("status", flat=True))
    assert statuses["offer"] > 0
    assert statuses["manual_review"] > 0
    assert statuses["declined"] > 0
    assert statuses["info_requested"] > 0
    assert statuses["issued"] > 0
    assert statuses["submitted"] == 0 and statuses["processing"] == 0  # nothing left hanging
    assert all(app.purpose.endswith(QUEUE_MARK) for app in Application.objects.all())


def test_personas_stay_clean_and_seeding_is_once(media):
    seed()
    seed_queue(10)
    persona_users = [p["username"] for p in persona_catalog()]
    assert not Application.objects.filter(
        company__memberships__user__username__in=persona_users
    ).exists()
    assert seed_queue(10) == 0
    assert Application.objects.count() == 10


def test_the_bank_sees_a_full_queue_after_seed_demo(media, settings):
    settings.DEMO_MODE = True
    call_command("seed_demo", "--queue", "12")
    bank = APIClient()
    bank.post("/api/demo/login", {"persona": "bank"}, format="json")
    page = bank.get("/api/bank/applications").json()
    assert page["count"] == 12
    assert sum(1 for row in page["results"] if row["hours_in_status"] > 24) > 0
    assert len({row["status"] for row in page["results"]}) >= 4
