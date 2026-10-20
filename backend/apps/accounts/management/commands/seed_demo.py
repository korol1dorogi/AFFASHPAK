from django.conf import settings
from django.core.management.base import BaseCommand

from apps.accounts.demo import seed


class Command(BaseCommand):
    help = "Create missing demo personas, companies and snapshots (synthetic, «демо»)."

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "--n-companies",
            type=int,
            default=0,
            help="Also seed this many generated companies besides the personas.",
        )
        parser.add_argument("--force", action="store_true", help="Seed even when DEMO_MODE is off.")

    def handle(self, *args, n_companies: int, force: bool, **options) -> None:
        if not (settings.DEMO_MODE or force):
            self.stdout.write("DEMO_MODE is off: nothing to seed.")
            return
        created = seed(n_companies)
        summary = ", ".join(f"{name} {count}" for name, count in created.items())
        self.stdout.write(f"Demo seed created: {summary}.")
