"""Celery entry points. With no broker the task runs in the request (CI and local compose).

In the request it must never break the response: the submit is already committed, so a
pipeline error is logged and the application stays where the pipeline left it.
"""

import logging

from django.conf import settings

logger = logging.getLogger(__name__)


def _eager() -> bool:
    return not getattr(settings, "CELERY_BROKER_URL", "") or settings.CELERY_TASK_ALWAYS_EAGER


def enqueue(application_id: int) -> None:
    if not settings.PIPELINE_ENABLED:
        return
    if _eager():
        from apps.pipeline.runner import execute

        try:
            execute(application_id)
        except Exception:
            logger.exception("pipeline could not start for application %s", application_id)
        return
    from apps.pipeline.celery_tasks import run_pipeline

    run_pipeline.delay(application_id)


def enqueue_disbursement(application_id: int) -> None:
    if not settings.PIPELINE_ENABLED:
        return
    from apps.applications.services import mark_issued

    if _eager():
        try:
            mark_issued(application_id)
        except Exception:
            logger.exception("disbursement failed for application %s", application_id)
        return
    from apps.pipeline.celery_tasks import disburse

    disburse.delay(application_id)
