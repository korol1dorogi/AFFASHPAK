"""The application's history in the logs (OPS5): one line per journal event.

Only ids and status codes — the event's message and payload stay in the database.
"""

import logging

from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.applications.models import ApplicationEvent

logger = logging.getLogger("apps.core.journal")


@receiver(post_save, sender=ApplicationEvent, dispatch_uid="core.log_application_event")
def log_application_event(sender, instance: ApplicationEvent, created: bool, **kwargs) -> None:
    if not created:
        return
    payload = instance.payload if isinstance(instance.payload, dict) else {}
    transition = (
        f"{instance.from_status} → {instance.to_status}"
        if instance.to_status
        else "status unchanged"
    )
    logger.info(
        "application %s event %s: %s, %s",
        instance.application_id,
        instance.kind,
        transition,
        instance.actor_kind,
        extra={
            "application_id": instance.application_id,
            "event_id": instance.pk,
            "kind": instance.kind,
            "from_status": instance.from_status,
            "to_status": instance.to_status,
            "actor_kind": instance.actor_kind,
            # check_completed: which source and how it answered — codes, not the source's data
            "source": payload.get("source"),
            "check_status": payload.get("status") if "source" in payload else None,
        },
    )
