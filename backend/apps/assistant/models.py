"""Assistant journal: every message and every tool call is stored (AGENTS.md, security 5)."""

import uuid

from django.conf import settings
from django.db import models

from apps.applications.models import Application


class MessageRole(models.TextChoices):
    USER = "user", "Пользователь"
    ASSISTANT = "assistant", "Ассистент"
    TOOL = "tool", "Инструмент"


class AssistantMessage(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="assistant_messages"
    )
    application = models.ForeignKey(
        Application, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    role = models.CharField(max_length=16, choices=MessageRole.choices)
    content = models.TextField(blank=True, default="")
    tool_calls = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("created_at", "id")

    def __str__(self) -> str:
        return f"{self.role}: {self.content[:40]}"


class PendingActionKind(models.TextChoices):
    CREATE_APPLICATION = "create_application", "Создать черновик заявки"
    SUBMIT_APPLICATION = "submit_application", "Отправить заявку"


class PendingActionStatus(models.TextChoices):
    PENDING = "pending", "Ждёт подтверждения"
    DONE = "done", "Выполнено"


class PendingAction(models.Model):
    """What the assistant proposed; runs only when the same user confirms it (AI1, AI3)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="assistant_actions"
    )
    kind = models.CharField(max_length=32, choices=PendingActionKind.choices)
    payload = models.JSONField(default=dict, blank=True)
    summary = models.TextField()
    application = models.ForeignKey(
        Application, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    status = models.CharField(
        max_length=16, choices=PendingActionStatus.choices, default=PendingActionStatus.PENDING
    )
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    confirmed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("created_at",)

    def __str__(self) -> str:
        return f"{self.kind}: {self.status}"
