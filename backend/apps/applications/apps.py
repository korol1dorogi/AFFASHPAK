from django.apps import AppConfig


class ApplicationsConfig(AppConfig):
    name = "apps.applications"
    label = "applications"

    def ready(self) -> None:
        from django.core import checks

        from apps.applications.sla import check_sla_hours

        checks.register(check_sla_hours)
