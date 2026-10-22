import django.db.models.deletion
import django.db.models.functions.text
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("business", "0005_restore_registry_names"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Invitation",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                ("username", models.CharField(max_length=150)),
                (
                    "role",
                    models.CharField(
                        choices=[("signatory", "Подписант"), ("preparer", "Готовит заявку")],
                        max_length=16,
                    ),
                ),
                ("position", models.CharField(max_length=100)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("pending", "Ждёт ответа"),
                            ("accepted", "Принято"),
                            ("declined", "Отклонено"),
                            ("cancelled", "Отозвано"),
                        ],
                        default="pending",
                        max_length=16,
                    ),
                ),
                ("created_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("responded_at", models.DateTimeField(blank=True, null=True)),
                (
                    "company",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="invitations",
                        to="business.company",
                    ),
                ),
                (
                    "invited_by",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="+",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ("created_at", "id"),
                "constraints": [
                    models.UniqueConstraint(
                        django.db.models.functions.text.Lower("username"),
                        models.F("company"),
                        condition=models.Q(("status", "pending")),
                        name="invitation_pending_company_username",
                    )
                ],
            },
        ),
    ]
