from django.core.management.base import BaseCommand

from apps.pipeline.recover import recover


class Command(BaseCommand):
    help = "Re-queue applications a lost pipeline or disbursement task left behind (recover.py)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--stale-seconds",
            type=int,
            default=60,
            help="Only applications that have been in their status at least this long.",
        )

    def handle(self, *args, stale_seconds: int, **options):
        done = recover(stale_seconds)
        for status, ids in done.items():
            self.stdout.write(f"{status}: {len(ids)} {ids if ids else ''}".rstrip())
