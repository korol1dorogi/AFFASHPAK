import logging

from celery import shared_task
from django.db import OperationalError

logger = logging.getLogger(__name__)

# The database blinked: try again; anything else is logged by Celery as a failed task and
# left to recover.py (the application row says what is still to be done).
RETRY = {"autoretry_for": (OperationalError,), "retry_backoff": True, "max_retries": 3}


@shared_task(name="pipeline.run", **RETRY)
def run_pipeline(application_id: int) -> None:
    from apps.pipeline.tasks import run_pipeline_once

    logger.info("pipeline.run in the worker for application %s", application_id)
    run_pipeline_once(application_id)


@shared_task(name="pipeline.disburse", **RETRY)
def disburse(application_id: int) -> None:
    from apps.pipeline.tasks import disburse_once

    logger.info("pipeline.disburse in the worker for application %s", application_id)
    disburse_once(application_id)
