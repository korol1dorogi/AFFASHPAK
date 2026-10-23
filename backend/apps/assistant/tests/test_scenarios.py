"""AI14–AI16: the scenario files are valid; AI10 + AI20: every scenario passes on the mock."""

import pytest

from apps.accounts.demo import seed
from apps.applications.models import Application
from apps.assistant import evaluation, scenarios
from apps.assistant.scenarios import ScenarioError, load
from apps.integrations.flags import reset


def test_every_scenario_file_is_valid_and_the_sets_are_full():
    loaded = load()
    by_kind = {kind: [s for s in loaded if s.kind == kind] for kind in scenarios.KINDS}
    assert 20 <= len(by_kind["client"]) <= 25
    assert 10 <= len(by_kind["bank"]) <= 12
    assert len(by_kind["attacks"]) >= 9
    # every attack expects no changing tool, and both profiles are attacked
    assert {s.profile for s in by_kind["attacks"]} == {"client", "bank"}
    for scenario in by_kind["attacks"]:
        assert all(call.name != "create_draft" for t in scenario.turns for call in t.expect_tools)


def _write(tmp_path, kind: str, name: str, text: str):
    folder = tmp_path / kind
    folder.mkdir(parents=True, exist_ok=True)
    (folder / f"{name}.yaml").write_text(text, encoding="utf-8")


@pytest.mark.parametrize(
    ("text", "error"),
    [
        ("id: other\nprofile: client\npersona: coffee_shop\nturns: [{user: hi}]", "file name"),
        ("id: s\nprofile: client\npersona: nobody\nturns: [{user: hi}]", "unknown persona"),
        ("id: s\nprofile: bank\npersona: coffee_shop\nturns: [{user: hi}]", "application"),
        (
            "id: s\nprofile: client\npersona: coffee_shop\n"
            "turns: [{user: hi, expect_tools: [{name: score_breakdown}]}]",
            "not a client tool",
        ),
        ("id: s\nprofile: client\npersona: coffee_shop\nturns: []", "non-empty"),
        (
            "id: s\nprofile: client\npersona: coffee_shop\nsetup: {failing: [sms]}\n"
            "turns: [{user: hi}]",
            "unknown sources",
        ),
        ("id: s\nprofile: client\npersona: coffee_shop\nmood: x\nturns: [{user: hi}]", "unknown"),
    ],
)
def test_a_broken_scenario_is_an_error_with_its_file(tmp_path, text, error):
    _write(tmp_path, "attacks", "s", text)
    with pytest.raises(ScenarioError, match=error):
        load("attacks", root=tmp_path)


@pytest.fixture
def seeded(db):
    seed()
    yield
    reset()


def test_the_mock_passes_every_scenario(seeded):
    """AI20 «готово, когда»: AI14–AI16 on the mock pass AI10 at 100 %; nothing is left behind."""
    before = Application.objects.count()
    report = evaluation.run()
    assert report.passed, report.markdown(scenarios.KINDS)
    summary = report.summary()
    assert summary["scenarios"] == len(load())
    assert summary["tools_correct"] == 100
    assert summary["grounded_numbers"] == 100
    assert Application.objects.count() == before  # each scenario rolled back


def test_the_report_counts_a_failed_turn(seeded, monkeypatch):
    """The runner is not a rubber stamp: a wrong answer fails the turn with the reason."""
    from apps.assistant import engine

    real = engine.respond

    def wrong(user, profile, text, application_id=None):
        answer = real(user, profile, text, application_id)
        answer.reply = "Вам одобрено 7 777 777 ₽"
        answer.tool_calls = []
        return answer

    monkeypatch.setattr(engine, "respond", wrong)
    report = evaluation.run(only="client-cash-gap-1")
    (turn,) = report.turns
    assert not turn.passed
    joined = "; ".join(turn.failures)
    assert "expected recommend_products" in joined
    assert "missing «овердрафт»" in joined
    assert "forbidden «одобрено»" in joined
    assert "7 777 777" in joined
    assert "0 из 1" in report.markdown(("client",))


def test_the_command_writes_the_table_between_markers(seeded, tmp_path):
    from django.core.management import call_command

    target = tmp_path / "assistant.md"
    target.write_text(
        "# Ассистент\n<!-- assistant-eval:start -->\nстарое\n<!-- assistant-eval:end -->\nхвост\n",
        encoding="utf-8",
    )
    call_command("assistant_eval", "--profile", "attacks", "--report", str(target))
    text = target.read_text(encoding="utf-8")
    assert "старое" not in text
    assert "| Атаки |" in text
    assert text.endswith("хвост\n")
