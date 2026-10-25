"""XP7: the policy in force and «what if a grade boundary moves» on the synthetic population."""

import pytest
from rest_framework.test import APIClient

from apps.core.factories import make_bank_user, make_user
from apps.core.testing import assert_matches_contract
from apps.scoring import population
from apps.scoring.policy import get_policy, get_scorecard

pytestmark = pytest.mark.django_db

CURRENT = {"A": 90, "B": 75, "C": 60, "D": 50}


@pytest.fixture
def bank():
    client = APIClient()
    client.force_authenticate(make_bank_user("bank_policy"))
    return client


def test_the_overview_shows_the_versions_in_force_and_the_population(bank):
    body = bank.get("/api/bank/policy").json()
    assert body["model_version"] == get_scorecard().model_version
    assert body["policy_version"] == get_policy().policy_version
    assert body["grades"] == [{"grade": g, "min_total": m} for g, m in CURRENT.items()]
    assert {f["name"] for f in body["factors"]} >= {"dscr", "debt_to_ebitda", "bki_history"}
    dscr = next(f for f in body["factors"] if f["name"] == "dscr")
    assert dscr["steps"][0] == {"threshold": "2.0", "points": 25}
    assert body["population"]["companies"] == 240
    assert sum(row["count"] for row in body["population"]["distribution"]) == 240
    assert sum(body["population"]["zones"].values()) == 240


def test_the_current_boundaries_change_nobody(bank):
    body = bank.post("/api/bank/policy/what-if", {"grades": CURRENT}, format="json").json()
    assert body["changed"] == 0
    assert body["before"] == body["after"]
    assert body["transitions"] == []


def test_a_lower_c_boundary_moves_d_to_c_and_nothing_else(bank):
    body = bank.post(
        "/api/bank/policy/what-if", {"grades": {**CURRENT, "C": 55}}, format="json"
    ).json()
    assert body["changed"] > 0
    assert {(t["from_grade"], t["to_grade"]) for t in body["transitions"]} == {("D", "C")}
    assert body["zones_after"] == body["zones_before"]  # C and D are both «manual»
    stopped = [row["count"] for row in body["before"] if row["grade"] == "stop"]
    assert stopped == [row["count"] for row in body["after"] if row["grade"] == "stop"]


def test_a_lower_d_boundary_turns_declines_into_manual_reviews(bank):
    body = bank.post(
        "/api/bank/policy/what-if", {"grades": {**CURRENT, "D": 40}}, format="json"
    ).json()
    assert body["zones_after"]["decline"] < body["zones_before"]["decline"]
    assert body["zones_after"]["manual"] > body["zones_before"]["manual"]
    assert body["changed"] == body["zones_before"]["decline"] - body["zones_after"]["decline"]


@pytest.mark.parametrize(
    "grades",
    [{**CURRENT, "B": 95}, {**CURRENT, "D": 60}, {**CURRENT, "A": 101}, {"A": 90, "B": 75}],
)
def test_boundaries_must_go_down(bank, grades):
    response = bank.post("/api/bank/policy/what-if", {"grades": grades}, format="json")
    assert response.status_code == 400


def test_a_client_never_sees_the_policy():
    client = APIClient()
    client.force_authenticate(make_user("client_policy"))
    assert client.get("/api/bank/policy").status_code == 403
    what_if = client.post("/api/bank/policy/what-if", {"grades": CURRENT}, format="json")
    assert what_if.status_code == 403
    assert APIClient().get("/api/bank/policy").status_code in (401, 403)


def test_the_population_is_scored_once():
    population.population.cache_clear()
    population.population()
    assert population.population.cache_info().misses == 1
    population.what_if(CURRENT)
    population.what_if({**CURRENT, "C": 50, "D": 40})
    assert population.population.cache_info().misses == 1


def test_both_answers_match_the_contract(bank):
    response = bank.get("/api/bank/policy")
    assert_matches_contract(response, method="GET", path="/api/bank/policy")
    body = {"grades": {**CURRENT, "C": 55}}
    response = bank.post("/api/bank/policy/what-if", body, format="json")
    assert_matches_contract(
        response, method="POST", path="/api/bank/policy/what-if", request_body=body
    )
    bad = {"grades": {**CURRENT, "D": 70}}
    response = bank.post("/api/bank/policy/what-if", bad, format="json")
    assert_matches_contract(
        response, method="POST", path="/api/bank/policy/what-if", request_body=bad
    )
