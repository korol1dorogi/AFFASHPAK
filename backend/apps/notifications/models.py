"""In-app notifications only: no email, SMS or messengers (case, O5)."""

from django.conf import settings
from django.db import models

from apps.applications.models import Application, EventKind


class Notification(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notifications"
    )
    application = models.ForeignKey(
        Application, on_delete=models.CASCADE, null=True, blank=True, related_name="+"
    )
    kind = models.CharField(max_length=32, choices=EventKind.choices)
    title = models.CharField(max_length=200)
    message = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("-created_at", "-id")
        indexes = (models.Index(fields=("user", "read_at")),)

    def __str__(self) -> str:
        return self.title
