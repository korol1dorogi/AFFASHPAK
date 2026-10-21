"""Celery entry points. With no broker the task runs in the request (CI and local compose)."""

from django.conf import settings


def _eager() -> bool:
    return not getattr(settings, "CELERY_BROKER_URL", "") or settings.CELERY_TASK_ALWAYS_EAGER


def enqueue(application_id: int) -> None:
    if not settings.PIPELINE_ENABLED:
        return
    if _eager():
        from apps.pipeline.runner import execute

        execute(application_id)
        return
    from apps.pipeline.celery_tasks import run_pipeline

    run_pipeline.delay(application_id)


def enqueue_disbursement(application_id: int) -> None:
    if not settings.PIPELINE_ENABLED:
        return
    from apps.applications.services import mark_issued

    if _eager():
        mark_issued(application_id)
        return
    from apps.pipeline.celery_tasks import disburse

    disburse.delay(application_id)
