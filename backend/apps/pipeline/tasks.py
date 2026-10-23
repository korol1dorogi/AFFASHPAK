"""Entry points: the Celery worker when a broker is set (compose), else in-process (pytest, init).

In the request it must never break the response: the submit is already committed, so a
pipeline error is logged and the application stays where the pipeline left it. A broker that
does not answer falls back to in-process, so an application never waits for a worker that
cannot get the task.

Every run is safe to repeat (a redelivered task, recover.py): the state machine refuses a
second transition, and that refusal means «already done», not an error.
"""

import logging

from django.conf import settings

from apps.applications.transitions import InvalidTransition

logger = logging.getLogger(__name__)


def _eager() -> bool:
    return not getattr(settings, "CELERY_BROKER_URL", "") or settings.CELERY_TASK_ALWAYS_EAGER


def run_pipeline_once(application_id: int) -> None:
    from apps.applications.models import Application
    from apps.pipeline.runner import execute

    try:
        execute(application_id)
    except Application.DoesNotExist:
        logger.warning("pipeline skipped: application %s no longer exists", application_id)
    except InvalidTransition:
        logger.info("pipeline skipped: application %s is already taken", application_id)


def disburse_once(application_id: int) -> None:
    from apps.applications.models import Application, ApplicationStatus, DisbursementStatus
    from apps.applications.services import mark_issued

    pending = Application.objects.filter(
        pk=application_id,
        status=ApplicationStatus.SIGNED,
        disbursement__status=DisbursementStatus.PENDING,
    ).exists()
    if not pending:
        logger.info("disbursement skipped: application %s has nothing to issue", application_id)
        return
    try:
        mark_issued(application_id)
    except InvalidTransition:
        logger.info("disbursement skipped: application %s is already issued", application_id)


def _send(task, application_id: int) -> bool:
    try:
        task.delay(application_id)
    except Exception:
        logger.exception(
            "broker unavailable: %s for application %s runs in-process instead of the worker",
            task.name,
            application_id,
        )
        return False
    logger.info("%s queued for application %s", task.name, application_id)
    return True


def enqueue(application_id: int) -> None:
    if not settings.PIPELINE_ENABLED:
        return
    if not _eager():
        from apps.pipeline.celery_tasks import run_pipeline

        if _send(run_pipeline, application_id):
            return
    try:
        run_pipeline_once(application_id)
    except Exception:
        logger.exception("pipeline could not start for application %s", application_id)


def enqueue_disbursement(application_id: int) -> None:
    if not settings.PIPELINE_ENABLED:
        return
    if not _eager():
        from apps.pipeline.celery_tasks import disburse

        if _send(disburse, application_id):
            return
    try:
        disburse_once(application_id)
    except Exception:
        logger.exception("disbursement failed for application %s", application_id)
