import logging
import os

from celery import Celery
from celery.signals import worker_init, worker_ready

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

app = Celery("alfa")
app.config_from_object("django.conf:settings", namespace="CELERY")
# Celery tasks live in <app>/celery_tasks.py; <app>/tasks.py is the in-process side.
app.autodiscover_tasks(related_name="celery_tasks")

logger = logging.getLogger(__name__)


@worker_init.connect
def _warm_simulators(**kwargs) -> None:
    """Build the synthetic sources before the pool forks: every child gets them ready, and the
    first application after a start is decided in ~50 ms, not ~2.5 s."""
    from apps.integrations.simulator_data import simulators

    simulators()


@worker_ready.connect
def _recover(**kwargs) -> None:
    """Finish what a lost task left behind (apps/pipeline/recover.py).

    One worker per stand (docker-compose*.yml): when it is ready nothing of its own runs yet,
    so every application still in «processing» was left by the previous run.
    """
    from django.db import connections

    from apps.pipeline.recover import recover

    try:
        recover(stale_seconds=0)
    except Exception:
        logger.exception("worker start: recovery failed; run `python manage.py pipeline_recover`")
    finally:
        connections.close_all()  # the main process keeps no connection the pool children share
