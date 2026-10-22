"""OPS4: the pipeline and the disbursement in a Celery worker — eager under pytest, a broker that
is down, repeated tasks, recovery of what a lost task left behind."""

import logging
import subprocess
import sys
from datetime import timedelta
from decimal import Decimal

import pytest
from django.conf import settings as django_settings
from django.core.management import call_command
from django.utils import timezone
from kombu.exceptions import OperationalError

from apps.applications.models import (
    Application,
    ApplicationStatus,
    Disbursement,
    DisbursementStatus,
    EventKind,
)
from apps.applications.transitions import InvalidTransition
from apps.pipeline import celery_tasks, runner, tasks
from apps.pipeline.recover import recover
from apps.pipeline.tests.test_personas import _application

S = ApplicationStatus


@pytest.fixture
def broker(settings):
    """Compose with Redis: tasks go to the worker instead of running here."""
    settings.CELERY_BROKER_URL = "redis://redis:6379/0"
    settings.CELERY_TASK_ALWAYS_EAGER = False


def _coffee_shop() -> Application:
    return _application("demo_coffee_shop", "overdraft_basic", "900000.00", 12)


def _in_status(application: Application, status: str, *, minutes_ago: int = 10) -> Application:
    Application.objects.filter(pk=application.pk).update(
        status=status, status_changed_at=timezone.now() - timedelta(minutes=minutes_ago)
    )
    application.refresh_from_db()
    return application


def _signed(application: Application, **kwargs) -> Application:
    Disbursement.objects.create(application=application, amount=Decimal("900000.00"))
    return _in_status(application, S.SIGNED, **kwargs)


def _issued_events(application: Application) -> int:
    return application.events.filter(kind=EventKind.ISSUED).count()


def test_pytest_runs_in_process_even_with_a_broker_in_the_environment():
    # compose sets CELERY_BROKER_URL for `docker compose run --rm backend pytest` too
    assert django_settings.TESTING
    assert django_settings.CELERY_BROKER_URL == ""
    assert django_settings.CELERY_TASK_ALWAYS_EAGER


def test_the_worker_knows_both_tasks():
    """A fresh process, as `celery -A config worker`: here the test imports already ran."""
    code = (
        "from config.celery import app; app.loader.import_default_modules(); "
        "print(sorted(name for name in app.tasks if name.startswith('pipeline.')))"
    )
    result = subprocess.run(  # noqa: S603 — a fixed command, no outside input
        [sys.executable, "-c", code],
        cwd=django_settings.BASE_DIR,
        capture_output=True,
        text=True,
        check=True,
    )
    assert result.stdout.strip() == "['pipeline.disburse', 'pipeline.run']"


@pytest.mark.django_db
def test_with_a_broker_the_pipeline_goes_to_the_worker(seeded, broker, monkeypatch):
    sent = []
    monkeypatch.setattr(celery_tasks.run_pipeline, "delay", sent.append)
    application = _coffee_shop()

    tasks.enqueue(application.pk)

    application.refresh_from_db()
    assert sent == [application.pk]
    assert application.status == S.SUBMITTED  # the worker takes it from here


@pytest.mark.django_db
def test_broker_down_runs_the_pipeline_in_process_and_says_so(seeded, broker, monkeypatch, caplog):
    def down(application_id):
        raise OperationalError("Error 111 connecting to redis:6379. Connection refused.")

    monkeypatch.setattr(celery_tasks.run_pipeline, "delay", down)
    application = _coffee_shop()

    with caplog.at_level(logging.ERROR, logger="apps.pipeline.tasks"):
        tasks.enqueue(application.pk)

    application.refresh_from_db()
    assert application.status == S.OFFER
    assert f"pipeline.run for application {application.pk} runs in-process" in caplog.text


@pytest.mark.django_db
def test_broker_down_issues_in_process(seeded, broker, monkeypatch):
    def down(application_id):
        raise OperationalError("Connection refused.")

    monkeypatch.setattr(celery_tasks.disburse, "delay", down)
    application = _signed(_coffee_shop())

    tasks.enqueue_disbursement(application.pk)

    application.refresh_from_db()
    assert application.status == S.ISSUED


@pytest.mark.django_db
def test_a_redelivered_pipeline_task_decides_once(seeded):
    application = _coffee_shop()

    celery_tasks.run_pipeline(application.pk)
    celery_tasks.run_pipeline(application.pk)

    application.refresh_from_db()
    assert application.status == S.OFFER
    assert application.decisions.count() == 1
    assert application.events.filter(to_status=S.PROCESSING).count() == 1


@pytest.mark.django_db
def test_two_deliveries_racing_for_the_start(seeded, monkeypatch):
    """Both saw «submitted»; the state machine lets one through, the other one just stops."""

    def taken(application_id):
        raise InvalidTransition()

    monkeypatch.setattr(runner, "start_processing", taken)
    application = _coffee_shop()

    celery_tasks.run_pipeline(application.pk)  # no exception: Celery would mark it failed

    application.refresh_from_db()
    assert application.status == S.SUBMITTED


@pytest.mark.django_db
def test_a_redelivered_disbursement_issues_once(seeded):
    application = _signed(_coffee_shop())

    celery_tasks.disburse(application.pk)
    celery_tasks.disburse(application.pk)

    application.refresh_from_db()
    assert application.status == S.ISSUED
    assert application.disbursement.status == DisbursementStatus.DONE
    assert _issued_events(application) == 1


@pytest.mark.django_db
def test_a_task_for_a_deleted_application_does_nothing(seeded):
    application = _coffee_shop()
    application_id = application.pk
    application.delete()  # /api/demo/reset while the task waited in the queue

    celery_tasks.run_pipeline(application_id)
    celery_tasks.disburse(application_id)


@pytest.mark.django_db
def test_recover_finishes_what_lost_tasks_left_behind(seeded):
    never_ran = _in_status(_coffee_shop(), S.SUBMITTED)
    died_mid_run = _in_status(_coffee_shop(), S.PROCESSING)
    not_issued = _signed(_coffee_shop())

    done = recover(stale_seconds=60)

    assert done == {
        "submitted": [never_ran.pk],
        "processing": [died_mid_run.pk],
        "signed": [not_issued.pk],
    }
    for application in (never_ran, died_mid_run, not_issued):
        application.refresh_from_db()
    assert never_ran.status == S.OFFER
    assert not_issued.status == S.ISSUED
    # a half-run pipeline is not repeated: an officer checks it, and it is not a decline
    assert died_mid_run.status == S.MANUAL_REVIEW
    decision = died_mid_run.decisions.get()
    assert decision.reasons[0]["message"] == runner.PIPELINE_FAILED


@pytest.mark.django_db
def test_recover_leaves_fresh_applications_to_their_tasks(seeded):
    fresh = _in_status(_coffee_shop(), S.PROCESSING, minutes_ago=0)
    queued = _signed(_coffee_shop(), minutes_ago=0)

    assert recover(stale_seconds=60) == {"submitted": [], "processing": [], "signed": []}

    fresh.refresh_from_db()
    queued.refresh_from_db()
    assert (fresh.status, queued.status) == (S.PROCESSING, S.SIGNED)


@pytest.mark.django_db
def test_recover_twice_changes_nothing_the_second_time(seeded):
    application = _signed(_coffee_shop())

    recover(stale_seconds=60)
    recover(stale_seconds=60)

    application.refresh_from_db()
    assert application.status == S.ISSUED
    assert _issued_events(application) == 1


@pytest.mark.django_db
def test_recover_command_prints_what_it_did(seeded, capsys):
    application = _in_status(_coffee_shop(), S.SUBMITTED)

    call_command("pipeline_recover", "--stale-seconds", "60")

    out = capsys.readouterr().out
    assert f"submitted: 1 [{application.pk}]" in out
    assert "processing: 0" in out
