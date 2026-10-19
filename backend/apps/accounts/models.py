from django.conf import settings
from django.db import models


class UserKind(models.TextChoices):
    CLIENT = "client", "Клиент"
    BANK = "bank", "Сотрудник банка"


class UserProfile(models.Model):
    """Which side the user is on. Bank users are bank_manager; admin = is_superuser only."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="profile"
    )
    kind = models.CharField(max_length=8, choices=UserKind.choices, default=UserKind.CLIENT)
    full_name = models.CharField(max_length=200, blank=True, default="")
    is_demo = models.BooleanField(default=False)

    def __str__(self) -> str:
        return f"{self.user} ({self.kind})"
