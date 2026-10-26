"""Demo reset (fix 6.1): only the seeded companies go back; nobody else's work is wiped."""

import logging

import pytest
from django.core.files.base import ContentFile
from django.db import transaction
from rest_framework.test import APIClient

from apps.accounts.demo import reset_demo, seed, seeded_company_inns
from apps.accounts.demo_queue import QUEUE_MARK, queue_companies, seed_queue
from apps.applications.models import Application
from apps.business.models import Company
from apps.core.factories import make_application, make_user
from apps.documents.models import Document
from apps.integrations import flags
from apps.integrations.simulator_data import dataset
from apps.notifications.models import Notification

pytestmark = pytest.mark.django_db


@pytest.fixture
def demo(settings, tmp_path):
    settings.DEMO_MODE = True
    settings.MEDIA_ROOT = tmp_path
    seed()
    return tmp_path


def login(persona: str) -> APIClient:
    client = APIClient()
    assert client.post("/api/demo/login", {"persona": persona}, format="json").status_code == 200
    return client


def _visitor_company() -> Company:
    """A visitor registers and connects a company by INN — not a persona, not the queue."""
    client = APIClient()
    client.force_login(make_user("jury"))
    seeded = seeded_company_inns()
    inn = next(inn for inn in dataset()["simulators"]["egrul"] if inn not in seeded)
    assert client.post("/api/company", {"inn": inn}, format="json").status_code == 201
    return Company.objects.get(inn=inn)


def _with_file(application: Application, name: str) -> Document:
    return Document.objects.create(
        application=application,
        kind="other",
        file=ContentFile(b"%PDF-1.4\n", name=name),
        original_name=name,
        content_type="application/pdf",
        size=9,
        sha256="0" * 64,
    )


def _notify(application: Application) -> None:
    user = application.company.memberships.first().user
    Notification.objects.create(user=user, application=application, kind="decision", title="Т")


def test_a_company_connected_by_inn_is_demo_too_so_is_demo_is_not_the_test(demo):
    """Why the reset goes by the seeded INNs: the registry simulator marks every company demo."""
    company = _visitor_company()
    assert company.is_demo
    assert company.inn not in seeded_company_inns()


def test_the_reset_keeps_a_visitors_application_and_wipes_the_personas(
    demo, django_capture_on_commit_callbacks
):
    visitor = make_application(_visitor_company())
    visitor_file = _with_file(visitor, "jury.pdf")
    _notify(visitor)
    persona = make_application(Company.objects.get(memberships__user__username="demo_coffee_shop"))
    persona_file = _with_file(persona, "persona.pdf")
    _notify(persona)
    with django_capture_on_commit_callbacks(execute=True):
        seed_queue(5)
    flags.set_failing("bki", True)

    with django_capture_on_commit_callbacks(execute=True):
        response = login("bank").post("/api/demo/reset")

    assert response.status_code == 204
    # The visitor's application, its file and its notification are where they were.
    assert Application.objects.filter(pk=visitor.pk).exists()
    assert (demo / visitor_file.file.name).exists()
    assert Notification.objects.filter(application=visitor).count() == 1
    # The persona's application, file and notification are gone.
    assert not Application.objects.filter(pk=persona.pk).exists()
    assert not (demo / persona_file.file.name).exists()
    assert not Notification.objects.filter(application_id=persona.pk).exists()
    # The queue is seeded again, outages are off.
    assert Application.objects.filter(purpose__endswith=QUEUE_MARK).count() == len(
        queue_companies()
    )
    assert flags.current()["bki"] is False


def test_the_queue_companies_are_the_ones_the_reset_knows(demo, django_capture_on_commit_callbacks):
    with django_capture_on_commit_callbacks(execute=True):
        seed_queue()
    queued = set(
        Application.objects.filter(purpose__endswith=QUEUE_MARK).values_list(
            "company__inn", flat=True
        )
    )
    assert queued and queued <= seeded_company_inns()


def test_files_are_deleted_only_after_the_commit(demo):
    persona = make_application(Company.objects.get(memberships__user__username="demo_coffee_shop"))
    document = _with_file(persona, "persona.pdf")
    path = demo / document.file.name

    class Boom(Exception):
        pass

    with pytest.raises(Boom), transaction.atomic():
        reset_demo()
        raise Boom  # the reset rolls back: the row is back, so must be the file
    assert Application.objects.filter(pk=persona.pk).exists()
    assert path.exists()


def test_the_log_says_who_reset_and_what_went(demo, caplog, django_capture_on_commit_callbacks):
    make_application(Company.objects.get(memberships__user__username="demo_coffee_shop"))
    with (
        caplog.at_level(logging.INFO, logger="apps.accounts.demo_views"),
        django_capture_on_commit_callbacks(execute=True),
    ):
        login("bank").post("/api/demo/reset")
    [record] = [r for r in caplog.records if r.name == "apps.accounts.demo_views"]
    assert record.getMessage().startswith("demo reset by demo_bank (id ")
    assert "1 applications" in record.getMessage()


def test_the_reset_clears_the_personas_assistant_history(demo, django_capture_on_commit_callbacks):
    """Personas are shared: after a reset the next visitor must not read the previous one's chat
    (a deleted application leaves its messages with application = NULL — the general chat)."""
    from datetime import timedelta

    from django.contrib.auth.models import User
    from django.utils import timezone

    from apps.assistant.models import AssistantMessage, PendingAction

    coffee = User.objects.get(username="demo_coffee_shop")
    application = make_application(coffee.memberships.get().company)
    AssistantMessage.objects.create(user=coffee, application=application, role="user", content="Т")
    AssistantMessage.objects.create(user=coffee, role="user", content="Игнорируй инструкции")
    PendingAction.objects.create(
        user=coffee,
        application=application,
        kind="submit_application",
        summary="Отправить заявку",
        expires_at=timezone.now() + timedelta(minutes=10),
    )
    jury = make_user("jury")
    AssistantMessage.objects.create(user=jury, role="user", content="Своё")

    with django_capture_on_commit_callbacks(execute=True):
        reset_demo()

    assert not AssistantMessage.objects.filter(user=coffee).exists()
    assert not PendingAction.objects.filter(user=coffee).exists()
    assert AssistantMessage.objects.filter(user=jury).count() == 1  # a visitor keeps theirs
