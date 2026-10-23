"""SRC5 rules on the scorecard level: С6 for suspended accounts, registry marks → reasons for an
officer; the scorecard itself (weights, points) stays the same."""

import copy
from datetime import date

import pytest

from apps.scoring import build_input, review_reasons, score, stop_factors


@pytest.fixture
def raw_edge(dataset):
    edges = {e["code"]: e for e in dataset["edge_cases"]}
    on_date = date.fromisoformat(dataset["meta"]["as_of"])

    def build(code: str, change=None):
        edge = copy.deepcopy(edges[code])
        if change is not None:
            change(edge["checks"])
        return build_input(edge["company"], edge["snapshot"], edge["checks"], on_date)

    return build


def _without_marks(checks):
    checks["transparent_business"]["data"]["accounts_suspended"] = False
    for flag in ("unreliable_address", "unreliable_director", "pending_exclusion"):
        checks["egrul"]["data"][flag] = False


def test_c6_declines_suspended_accounts(raw_edge):
    stops = stop_factors(raw_edge("e_accounts_suspended"))
    assert [stop.code for stop in stops] == ["С6"]
    assert stops[0].reason.metric == "accounts_suspended"
    assert stops[0].reason.message.startswith("ФНС приостановила операции по счетам")
    assert stops[0].improvement.startswith("Снимите приостановку")


@pytest.mark.parametrize("status", ["restricted", "unavailable"])
def test_c6_does_not_read_hidden_or_missing_data(raw_edge, status):
    def hide(checks):
        checks["transparent_business"]["status"] = status

    assert stop_factors(raw_edge("e_accounts_suspended", hide)) == []


def test_a_registry_mark_does_not_change_the_score(raw_edge):
    with_mark = score(raw_edge("e_unreliable_address"))
    clean = score(raw_edge("e_unreliable_address", _without_marks))
    assert (with_mark.total, with_mark.grade) == (clean.total, clean.grade)
    assert with_mark.factors_payload() == clean.factors_payload()


def test_suspended_accounts_decline_before_scoring(raw_edge):
    with pytest.raises(ValueError, match="С6"):  # a stop factor never reaches the scorecard
        score(raw_edge("e_accounts_suspended"))
    clean = score(raw_edge("e_accounts_suspended", _without_marks))
    assert clean.grade == "A"  # the base persona 1 scores as before


def test_unreliable_address_is_a_reason_for_an_officer_not_a_stop(raw_edge):
    inp = raw_edge("e_unreliable_address")
    assert stop_factors(inp) == []
    reasons = review_reasons(inp)
    assert [r.metric for r in reasons] == ["egrul_unreliable_address"]
    assert reasons[0].passed is False
    assert reasons[0].message.endswith("Это не отказ")


def test_every_registry_mark_gives_its_own_reason(raw_edge):
    def all_marks(checks):
        for flag in ("unreliable_address", "unreliable_director", "pending_exclusion"):
            checks["egrul"]["data"][flag] = True

    metrics = [r.metric for r in review_reasons(raw_edge("e_unreliable_address", all_marks))]
    assert metrics == [
        "egrul_unreliable_address",
        "egrul_unreliable_director",
        "egrul_pending_exclusion",
    ]


@pytest.mark.parametrize("status", ["not_found", "failed", "restricted", "unavailable"])
def test_registry_marks_are_not_read_without_registry_data(raw_edge, status):
    def no_registry(checks):
        checks["egrul"]["status"] = status

    assert review_reasons(raw_edge("e_unreliable_address", no_registry)) == []


@pytest.mark.parametrize("code", ["e_accounts_suspended", "g2", "g7", "e_no_debt"])
def test_clean_registry_gives_no_reasons(raw_edge, code):
    assert review_reasons(raw_edge(code)) == []
