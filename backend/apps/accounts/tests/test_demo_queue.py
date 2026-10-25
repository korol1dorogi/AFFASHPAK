"""A fresh stand has a living bank queue: population applications decided by the real pipeline."""

from collections import Counter

import pytest
from django.core.management import call_command
from rest_framework.test import APIClient

from apps.accounts.demo import persona_catalog, seed
from apps.accounts.demo_queue import (
    PLAN,
    QUEUE_MARK,
    plan_position,
    queue_companies,
    queue_size,
    seed_queue,
)
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


# ───────────────────────── fix 3.1: one shift for every date ─────────────────────────

# Moments that are not «when it happened» but «until when»: they move by the shift too,
# but lie in the future on purpose.
DEADLINES = {"expires_at"}


def _moments(application: Application) -> dict[str, list]:
    """Every timestamp of the application and of the rows that belong to it."""
    from apps.accounts.demo_queue import _related_to_application, _timestamps

    found = {
        f"Application.{name}": [getattr(application, name)] for name in _timestamps(Application)
    }
    for model, link in _related_to_application():
        for name in _timestamps(model):
            if name in DEADLINES:
                continue
            values = model.objects.filter(**{link: application}).values_list(name, flat=True)
            found[f"{model.__name__}.{name}"] = list(values)
    # Not happened yet (no decision, not read): nothing to age.
    return {name: [v for v in values if v is not None] for name, values in found.items()}


@pytest.mark.django_db(transaction=True)  # real commits: the disbursement runs as on the stand
def test_every_date_of_a_queue_application_is_aged_by_the_same_shift(media):
    from datetime import timedelta

    from apps.applications.models import Offer
    from apps.applications.offers import OFFER_TTL

    seed()
    assert seed_queue(12) == 12
    slack = timedelta(minutes=1)  # one application is seeded within seconds
    aged = 0
    for application in Application.objects.filter(purpose__endswith=QUEUE_MARK):
        start, end = application.created_at, application.status_changed_at
        for name, values in _moments(application).items():
            for value in values:
                # Nothing after the last status change, nothing before the draft: no «13:47»
                # offer or check on an application decided at «06:47».
                assert start - slack <= value <= end + slack, (application.pk, name, value)
        aged += end < application.submitted_at + slack and end < start + timedelta(days=3)
    assert aged == 12
    # «Действует до» stays 30 days after the offer, wherever the offer moved.
    for offer in Offer.objects.filter(application__purpose__endswith=QUEUE_MARK):
        assert abs(offer.expires_at - offer.created_at - OFFER_TTL) < slack
    # The shift is real: the oldest application was decided more than a day ago.
    oldest = min(Application.objects.values_list("status_changed_at", flat=True))
    from django.utils import timezone

    assert timezone.now() - oldest > timedelta(days=1)
    issued = Application.objects.filter(purpose__endswith=QUEUE_MARK, status="issued")
    assert issued.exists()  # the disbursement is covered by the check above


# ───────────────────────── UX6: a queue of 300 ─────────────────────────


def test_the_queue_size_comes_from_the_settings(settings):
    settings.DEMO_QUEUE_SIZE = 0
    assert queue_size() == 30
    settings.DEMO_QUEUE_SIZE = 300
    assert queue_size() == 300


def test_a_queue_larger_than_the_population_goes_round_again():
    companies = queue_companies(300)
    distinct = len({c["_key"] for c in companies})
    assert len(companies) == 300
    assert distinct == 240  # the generated population
    # the same company's second application asks for another product
    for index in range(300 - distinct):
        first = PLAN[plan_position(index, distinct) % len(PLAN)][0]
        second = PLAN[plan_position(index + distinct, distinct) % len(PLAN)][0]
        assert companies[index]["_key"] == companies[index + distinct]["_key"]
        assert first != second
