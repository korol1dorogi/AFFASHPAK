from django.conf import settings
from django.db import models


class LegalForm(models.TextChoices):
    IP = "ip", "ИП"
    OOO = "ooo", "ООО"


class Business(models.Model):
    """Company owned by one client. Every child row is reached through this owner."""

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="businesses",
    )
    legal_form = models.CharField(max_length=3, choices=LegalForm.choices)
    name = models.CharField(max_length=300)
    inn = models.CharField(max_length=12)
    ogrn = models.CharField(max_length=15)
    okved = models.CharField(max_length=16)
    registered_at = models.DateField()
    region = models.CharField(max_length=128)
    is_demo = models.BooleanField(default=False)

    def __str__(self) -> str:
        return self.name
