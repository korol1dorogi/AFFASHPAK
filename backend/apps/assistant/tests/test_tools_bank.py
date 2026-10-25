"""AI17: the bank officer's tools — read only, bank_manager only, the pipeline's own figures."""

import json
import re
from decimal import Decimal

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext

from apps.accounts.demo import seed
from apps.applications.models import BkiConsent, Score
from apps.assistant import tools, tools_bank
from apps.assistant.tools_bank import TOOLS, run_tool
from apps.business.models import Membership
from apps.core.factories import make_bank_user
from apps.integrations.flags import reset
from apps.pipeline.runner import execute

from .personas import persona_application

pytestmark = pytest.mark.django_db

WRITE = re.compile(r"^\s*(INSERT|UPDATE|DELETE)\b", re.IGNORECASE)


@pytest.fixture
def seeded(db):
    seed()
    yield
    reset()


@pytest.fixture
def bank(seeded):
    return make_bank_user("bank_tools_ai17")


def args_for(name: str, application_id: int) -> dict:
    if name == "draft_officer_comment":
        return {"application_id": application_id, "preliminary_intent": "request_info"}
    return {"application_id": application_id}


# ───────────────────────── read only, bank only ─────────────────────────


@pytest.mark.parametrize("number", [1, 3, 4, 5, 6])
def test_no_tool_writes_to_the_database(bank, number):
    application = persona_application(number)
    with CaptureQueriesContext(connection) as queries:
        for name in TOOLS:
            result = run_tool(bank, name, args_for(name, application.pk))
            assert "error" not in result, (name, result)
            json.dumps(result)  # the journal stores it as JSON: no Decimal, no datetime inside
    writes = [q["sql"] for q in queries.captured_queries if WRITE.match(q["sql"])]
    assert writes == []


@pytest.mark.parametrize("name", list(TOOLS))
def test_a_client_gets_not_found_from_every_bank_tool(bank, name):
    application = persona_application(1)
    coffee = Membership.objects.get(user__username="demo_coffee_shop").user
    result = run_tool(coffee, name, args_for(name, application.pk))  # even their own application
    assert result["error"]["code"] == "not_found"


@pytest.mark.parametrize("name", list(TOOLS))
def test_an_unknown_application_is_not_found_and_the_id_is_required(bank, name):
    assert run_tool(bank, name, args_for(name, 999_999))["error"]["code"] == "not_found"
    missing = run_tool(bank, name, {})
    assert missing["error"]["code"] == "invalid"
    assert "application_id" in missing["error"]["details"]


def test_the_two_sets_do_not_mix(bank):
    application = persona_application(1)
    coffee = Membership.objects.get(user__username="demo_coffee_shop").user
    for name in TOOLS:
        assert tools.run_tool(coffee, name, {})["error"]["code"] == "unknown_tool"
    for name in tools.TOOLS:
        assert run_tool(bank, name, {"application_id": application.pk})["error"]["code"] == (
            "unknown_tool"
        )


def test_every_bank_tool_is_strict_and_named_in_the_bank_prompt():
    from apps.assistant import prompts

    text = prompts.load("bank").text
    for name, tool in TOOLS.items():
        assert name in text
        assert tool.spec.parameters["additionalProperties"] is False
        assert "application_id" in tool.spec.parameters["required"]


# ───────────────────────── the figures are the pipeline's ─────────────────────────


def test_application_summary_of_persona_4(bank):
    application = persona_application(4)
    result = run_tool(bank, "application_summary", {"application_id": application.pk})

    assert result["status"] == "manual_review"
    assert result["status_label"] == "У сотрудника банка"
    assert result["decision"]["grade"] == "C"
    assert result["decision"]["is_preliminary"] is True
    assert result["requested_amount"] == "8000000.00"
    assert result["product"]["code"] == "investment_loan_basic"
    assert set(result["checks"]) == {"egrul", "transparent_business", "bki", "bank_account"}
    assert result["sla"]["due_at"] is not None  # manual review has a norm (XP4)
    assert result["client_text"]["purpose"] == application.purpose
    assert result["client_text"]["company_name"] == application.company.name
    assert "purpose" not in result  # typed text travels only inside client_text


def test_checks_carry_provenance(bank):
    application = persona_application(1)
    result = run_tool(bank, "checks_with_provenance", {"application_id": application.pk})
    assert len(result["checks"]) == 4
    for check in result["checks"]:
        assert check["received_at"] is not None
        assert len(check["response_sha256"]) == 12
        assert check["meaning"]
    assert "не негатив" in result["note"]


def test_no_consent_is_not_a_negative_for_the_bank(bank):
    application = persona_application(1, run=False)
    BkiConsent.objects.filter(application=application).delete()
    execute(application.pk)
    checks = run_tool(bank, "checks_with_provenance", {"application_id": application.pk})
    bki = next(c for c in checks["checks"] if c["source"] == "bki")
    assert bki["status"] == "consent_missing"
    assert "не негатив" in bki["meaning"]
    asks = run_tool(bank, "missing_documents", {"application_id": application.pk})
    assert any("Согласие на запрос в БКИ" in item["ask"] for item in asks["because_of_sources"])
    policy = run_tool(bank, "policy_compare", {"application_id": application.pk})
    assert [item["source"] for item in policy["no_data"]] == ["bki"]


def test_score_breakdown_adds_up_to_the_stored_score(bank):
    application = persona_application(4)
    score = Score.objects.get(application=application)
    result = run_tool(bank, "score_breakdown", {"application_id": application.pk})

    assert (result["grade"], result["total"]) == ("C", 65) == (score.grade, score.total)
    assert sum(f["points"] for f in result["factors"]) == score.total
    assert all(f["max_points"] is not None for f in result["factors"])
    lost = [f["lost_points"] for f in result["factors"]]
    assert lost == sorted(lost, reverse=True)  # the heaviest losses first
    assert result["grade_zone"] == "ручное рассмотрение"


def test_score_breakdown_of_a_stop_factor_says_there_is_none(bank):
    application = persona_application(6)
    result = run_tool(bank, "score_breakdown", {"application_id": application.pk})
    assert result["score"] is None
    assert "стоп-фактором" in result["message"]


def test_dscr_limits_are_the_decision_figures(bank):
    application = persona_application(3)  # counteroffer capped by DSCR
    result = run_tool(bank, "dscr_and_limits", {"application_id": application.pk})
    decision = application.decisions.get()
    stored = {r["metric"]: r for r in decision.reasons}
    limits = {r["metric"]: r for r in result["limits"]}

    assert limits["max_loan_by_dscr"] == stored["max_loan_by_dscr"]
    assert Decimal(limits["max_loan_by_dscr"]["value"]) == application.offers.get().amount
    assert limits["dscr_after"] == stored["dscr_after"]
    assert result["min_dscr"] in ("1.25", Decimal("1.25"), "1.2500")
    assert result["dscr_now"]["value"] is not None


def test_policy_compare_finds_the_stop_factor(bank):
    application = persona_application(6)
    result = run_tool(bank, "policy_compare", {"application_id": application.pk})
    assert [stop["code"] for stop in result["stop_factors"]] == ["С1 ликвидация или банкротство"]
    assert result["grade"] is None


def test_policy_compare_of_a_clean_offer(bank):
    application = persona_application(1)
    result = run_tool(bank, "policy_compare", {"application_id": application.pk})
    assert result["stop_factors"] == []
    assert result["no_data"] == []
    assert result["grade_zone"] == "автоматическое предложение"
    by_rule = {row["rule"]: row for row in result["rows"]}
    assert by_rule["requested_amount"]["passed"] is True
    assert by_rule["term_months"]["passed"] is True


def test_missing_documents_of_persona_4_without_an_invoice(bank):
    application = persona_application(4, run=False)
    application.documents.filter(kind="invoice").delete()
    result = run_tool(bank, "missing_documents", {"application_id": application.pk})
    assert [doc["kind"] for doc in result["missing_product_documents"]] == ["invoice"]
    assert result["field_gaps"] == []


# ───────────────────────── draft comment under a PRELIMINARY intent ─────────────────────────


@pytest.mark.parametrize("intent", ["approve", "counteroffer", "request_info", "decline"])
def test_the_draft_says_it_is_preliminary_and_saves_nothing(bank, intent):
    application = persona_application(4)
    result = run_tool(
        bank,
        "draft_officer_comment",
        {"application_id": application.pk, "preliminary_intent": intent},
    )
    assert result["preliminary_intent"] == intent
    assert result["draft_comment"].startswith("Предварительно склоняюсь")
    assert "это не решение" in result["draft_comment"]
    assert result["is_saved"] is False
    assert "Грейд C (65 из 100)." in result["draft_comment"]


def test_counteroffer_draft_names_the_dscr_cap(bank):
    application = persona_application(3)
    result = run_tool(
        bank,
        "draft_officer_comment",
        {"application_id": application.pk, "preliminary_intent": "counteroffer"},
    )
    assert "Денежный поток выдерживает до 2" in result["draft_comment"].replace("\xa0", " ")


def test_approving_grade_e_or_a_stop_factor_warns(bank):
    declined = persona_application(5)
    result = run_tool(
        bank, "draft_officer_comment",
        {"application_id": declined.pk, "preliminary_intent": "approve"},
    )  # fmt: skip
    assert any("Грейд E" in warning for warning in result["warnings"])
    stopped = persona_application(6)
    result = run_tool(
        bank, "draft_officer_comment",
        {"application_id": stopped.pk, "preliminary_intent": "approve"},
    )  # fmt: skip
    assert any("стоп-фактор" in warning for warning in result["warnings"])


def test_declining_only_for_missing_data_warns_by_src3(bank, settings):
    from apps.integrations.flags import set_failing

    set_failing("bki", True)
    application = persona_application(1)  # BKI down → manual review, nothing failed
    result = run_tool(
        bank,
        "draft_officer_comment",
        {"application_id": application.pk, "preliminary_intent": "decline"},
    )
    assert any("SRC3" in warning for warning in result["warnings"])


def test_the_intent_must_be_one_of_four(bank):
    application = persona_application(1)
    result = run_tool(
        bank,
        "draft_officer_comment",
        {"application_id": application.pk, "preliminary_intent": "issue_money"},
    )
    assert result["error"]["code"] == "invalid"
    assert "preliminary_intent" in result["error"]["details"]


def test_tools_bank_reuses_the_client_status_words():
    assert tools_bank.STATUS_TEXT is tools.STATUS_TEXT
