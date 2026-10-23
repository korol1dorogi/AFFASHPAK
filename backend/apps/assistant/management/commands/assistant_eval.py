"""manage.py assistant_eval — the assistant's quality on the scenarios (AI10).

    python manage.py assistant_eval                          # all scenarios on the mock
    python manage.py assistant_eval --profile attacks --provider openai --pause 5
    python manage.py assistant_eval --report ../docs/assistant.md   # rewrite the quality table

--provider openai uses LLM_BASE_URL, LLM_API_KEY and LLM_MODEL of the .env. Every scenario runs
in a transaction rolled back at the end, so the command is safe on the stand. Exit code 1 when a
turn fails (--fail-under lowers the bar for a live model).
"""

import pathlib

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.assistant import evaluation
from apps.assistant.scenarios import KINDS

START = "<!-- assistant-eval:start -->"
END = "<!-- assistant-eval:end -->"


class Command(BaseCommand):
    help = "Run the assistant scenarios (client, bank, attacks) and measure the quality."

    def add_arguments(self, parser):
        parser.add_argument("--profile", choices=[*KINDS, "all"], default="all")
        parser.add_argument("--provider", choices=["mock", "openai"], default="mock")
        parser.add_argument("--scenario", help="Only this scenario id.")
        parser.add_argument(
            "--pause",
            type=float,
            default=0.0,
            help="Seconds between scenarios (a free tier's rate limit).",
        )
        parser.add_argument("--report", help="Markdown file whose quality table is rewritten.")
        parser.add_argument("--json", help="Write every turn with its answer to this file.")
        parser.add_argument(
            "--fail-under",
            type=int,
            default=100,
            help="Least share of passed turns, %% (default 100).",
        )

    def handle(self, *args, **options):
        provider = options["provider"]
        if provider == "openai" and not (settings.LLM_BASE_URL and settings.LLM_MODEL):
            raise CommandError("--provider openai needs LLM_BASE_URL and LLM_MODEL in .env")
        settings.LLM_PROVIDER = provider  # this process only
        kind = None if options["profile"] == "all" else options["profile"]
        try:
            report = evaluation.run(
                kind,
                only=options["scenario"],
                provider=provider,
                model=settings.LLM_MODEL if provider == "openai" else "",
                pause=options["pause"],
            )
        except evaluation.EvalSetupError as error:
            raise CommandError(str(error)) from error

        kinds = KINDS if kind is None else (kind,)
        table = report.markdown(kinds)
        self.stdout.write(table)
        if options["json"]:
            pathlib.Path(options["json"]).write_text(report.as_json(), encoding="utf-8")
        if options["report"]:
            _rewrite(pathlib.Path(options["report"]), table)
            self.stdout.write(f"Таблица записана в {options['report']}")

        summary = report.summary()
        share = round(100 * summary["turns_passed"] / summary["turns"]) if summary["turns"] else 0
        if share < options["fail_under"]:
            raise CommandError(f"passed {share} % of turns, need {options['fail_under']} %")


def _rewrite(path: pathlib.Path, table: str) -> None:
    """Replace the block between the markers; no markers — append the block."""
    text = path.read_text(encoding="utf-8") if path.exists() else ""
    block = f"{START}\n{table}{END}"
    if START in text and END in text:
        head, _, rest = text.partition(START)
        _, _, tail = rest.partition(END)
        text = head + block + tail
    else:
        text = text.rstrip("\n") + ("\n\n" if text else "") + block + "\n"
    path.write_text(text, encoding="utf-8", newline="\n")
