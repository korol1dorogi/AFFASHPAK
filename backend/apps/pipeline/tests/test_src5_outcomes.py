"""SRC5 through the pipeline: suspended accounts → decline С6; ЕГРЮЛ marks → an officer."""

import pytest

from apps.applications.models import Application, Score
from apps.integrations import adapters
from apps.integrations.breaker import breaker
from apps.pipeline.runner import execute
from apps.pipeline.tests.test_personas import _application, _documents


@pytest.fixture(autouse=True)
def _fresh_breaker():
    breaker.reset()
    yield
    breaker.reset()


@pytest.fixture
def mark(monkeypatch):
    """Set keys in one source's real simulator answer (and its status, if given)."""

    def install(source: str, status: str | None = None, **data) -> None:
        real = adapters._answer

        def fake(asked, inn, *, has_account):
            answer = real(asked, inn, has_account=has_account)
            if asked != source:
                return answer
            return {
                "status": status or answer["status"],
                "data": {**answer["data"], **data},
            }

        monkeypatch.setattr(adapters, "_answer", fake)

    return install


def _run() -> tuple[Application, object]:
    application = _application("demo_coffee_shop", "overdraft_basic", "900000.00", 12)
    _documents(application, tuple(application.product.required_documents))
    execute(application.pk)
    application.refresh_from_db()
    return application, application.decisions.get()


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("flag", "metric"),
    [
        ("unreliable_address", "egrul_unreliable_address"),
        ("pending_exclusion", "egrul_pending_exclusion"),
    ],
)
def test_a_registry_mark_sends_persona_1_to_an_officer(seeded, mark, flag, metric):
    mark("egrul", "warning", **{flag: True})
    application, decision = _run()

    assert (application.status, decision.outcome) == ("manual_review", "manual_review")
    assert not application.source_unavailable  # the registry answered: no outage mark
    row = next(r for r in decision.reasons if r["metric"] == metric)
    assert row["passed"] is False
    assert row["message"].endswith("Это не отказ")
    assert Score.objects.get(application=application).grade == "A"  # scored as usual


@pytest.mark.django_db
def test_suspended_accounts_decline_with_c6(seeded, mark):
    mark("transparent_business", "warning", accounts_suspended=True)
    application, decision = _run()

    assert (application.status, decision.outcome) == ("declined", "declined")
    assert [r["metric"] for r in decision.reasons] == ["accounts_suspended"]
    assert decision.improvements == [
        "Снимите приостановку операций по счетам в ФНС и подайте заявку снова"
    ]
    assert not Score.objects.filter(application=application).exists()  # a stop is not scored


@pytest.mark.django_db
def test_clean_marks_keep_persona_1_offer(seeded, mark):
    mark("egrul", unreliable_address=False, unreliable_director=False, pending_exclusion=False)
    mark("transparent_business", accounts_suspended=False)
    _, decision = _run()
    assert decision.outcome == "offer"
