import logging
import os

from celery import Celery
from celery.signals import (
    before_task_publish,
    setup_logging,
    task_postrun,
    task_prerun,
    worker_init,
    worker_ready,
)

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


# --- Correlation (OPS5): the request_id of the client's request follows its task into the worker,
# so `grep <request_id>` shows an application from the submit to the decision. ---

# Tasks whose first argument is the application's id (apps/pipeline/celery_tasks.py)
APPLICATION_TASKS = frozenset({"pipeline.run", "pipeline.disburse"})
_bound: dict[str, list] = {}


@setup_logging.connect
def _logging(**kwargs) -> None:
    """The worker logs through settings.LOGGING (JSON, correlation fields), not Celery's own."""
    from logging.config import dictConfig

    from django.conf import settings

    dictConfig(settings.LOGGING)


@before_task_publish.connect
def _publish_request_id(headers: dict | None = None, **kwargs) -> None:
    """A task queued without a request (recover() at the worker start) gets its own id; its
    lines still carry the application_id."""
    from apps.core import context

    if headers is not None:
        headers["request_id"] = context.request_id.get() or context.new_request_id("task")


def _application_id(task, args, kwargs) -> int | None:
    value = (kwargs or {}).get("application_id")
    if value is None and task.name in APPLICATION_TASKS and args:
        value = args[0]
    return value if isinstance(value, int) else None


def _incoming_request_id(task) -> str | None:
    request = task.request
    value = getattr(request, "request_id", None) or (getattr(request, "headers", None) or {}).get(
        "request_id"
    )
    from apps.core import context

    return value if context.is_valid_request_id(value) else None


@task_prerun.connect
def _bind_task_context(task_id=None, task=None, args=None, kwargs=None, **extra) -> None:
    from apps.core import context

    # eager (pytest, init): nothing was published — keep the request's own id
    request_id = (
        _incoming_request_id(task) or context.request_id.get() or context.new_request_id("task")
    )
    application_id = _application_id(task, args, kwargs) or context.application_id.get()
    _bound[task_id] = context.bind(request_id=request_id, application_id=application_id)


@task_postrun.connect
def _unbind_task_context(task_id=None, **extra) -> None:
    """Restore what was there before the task — the request's context in eager mode."""
    from apps.core import context

    tokens = _bound.pop(task_id, None)
    if tokens is not None:
        context.reset(tokens)
