from celery import shared_task


@shared_task(name="pipeline.run")
def run_pipeline(application_id: int) -> None:
    from apps.pipeline.runner import execute

    execute(application_id)


@shared_task(name="pipeline.disburse")
def disburse(application_id: int) -> None:
    from apps.applications.services import mark_issued

    mark_issued(application_id)
