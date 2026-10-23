"""Finish what a lost task left behind. The application row is the source of truth, not the queue.

- submitted — the pipeline never ran (Redis lost the message, the worker was down): queue it again;
- processing — the worker died mid-run: an officer checks it (as on any pipeline error, not a
  decline); the run is not repeated, its checks may be half-written;
- signed with a pending disbursement — queue the disbursement again.

Safe to run any time: a duplicate task finds the status already moved and does nothing.
Runs when the worker starts (config/celery.py) and by hand: `python manage.py pipeline_recover`.
"""

import logging
from datetime import timedelta

from django.utils import timezone

from apps.applications.models import Application, ApplicationStatus, DisbursementStatus

S = ApplicationStatus
logger = logging.getLogger(__name__)


def recover(stale_seconds: int) -> dict[str, list[int]]:
    from apps.pipeline.runner import to_officer
    from apps.pipeline.tasks import enqueue, enqueue_disbursement

    before = timezone.now() - timedelta(seconds=stale_seconds)
    stale = Application.objects.filter(status_changed_at__lte=before).order_by("pk")
    done = {
        "submitted": list(stale.filter(status=S.SUBMITTED).values_list("pk", flat=True)),
        "processing": list(stale.filter(status=S.PROCESSING).values_list("pk", flat=True)),
        "signed": list(
            stale.filter(
                status=S.SIGNED, disbursement__status=DisbursementStatus.PENDING
            ).values_list("pk", flat=True)
        ),
    }
    for application_id in done["submitted"]:
        enqueue(application_id)
    for application_id in done["processing"]:
        to_officer(application_id)
    for application_id in done["signed"]:
        enqueue_disbursement(application_id)
    if any(done.values()):
        logger.warning("pipeline recovery: %s", done)
    return done
