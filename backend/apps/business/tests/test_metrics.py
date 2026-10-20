"""GET /api/company/metrics: snapshot + key metrics as Reason, only for the user's own company."""

import pytest
from django.contrib.auth.models import User
from rest_framework.test import APIClient

from apps.accounts.demo import seed
from apps.core.factories import make_bank_user, make_company, make_user
from apps.core.testing import assert_matches_contract

pytestmark = pytest.mark.django_db
PATH = "/api/company/metrics"
METRICS = [
    "business_age_months",
    "dscr",
    "debt_to_ebitda",
    "revenue_trend",
    "counterparty_concentration",
]


def as_user(user) -> APIClient:
    client = APIClient()
    client.force_login(user)
    return client


def test_persona_1_sees_its_snapshot_and_explained_metrics():
    seed()
    response = as_user(User.objects.get(username="demo_coffee_shop")).get(PATH)
    assert response.status_code == 200
    assert_matches_contract(response, method="get", path=PATH)
    body = response.json()
    assert body["is_demo"] is True
    assert body["snapshot"]["cfads"] == "450000.00"  # data-spec.md §9.2
    metrics = {reason["metric"]: reason for reason in body["metrics"]}
    assert list(metrics) == METRICS
    assert metrics["dscr"]["passed"] is True and metrics["dscr"]["value"] is None  # no debts
    assert metrics["revenue_trend"]["value"] == "1.0500"
    assert metrics["counterparty_concentration"]["value"] == "0.1000"
    assert all(reason["message"] for reason in body["metrics"])


def test_without_a_snapshot_metrics_are_null_not_zero():
    owner = make_user("owner")
    make_company(members={owner: "signatory"})
    response = as_user(owner).get(PATH)
    assert response.status_code == 200
    assert_matches_contract(response, method="get", path=PATH)
    body = response.json()
    assert body["snapshot"] is None
    by_metric = {reason["metric"]: reason for reason in body["metrics"]}
    for metric in ("dscr", "debt_to_ebitda", "revenue_trend", "counterparty_concentration"):
        assert by_metric[metric]["value"] is None
    assert by_metric["business_age_months"]["value"] is not None


def test_each_client_gets_only_their_own_company():
    seed()
    coffee = as_user(User.objects.get(username="demo_coffee_shop")).get(PATH).json()
    garden = as_user(User.objects.get(username="demo_garden_store")).get(PATH).json()
    assert coffee["snapshot"]["id"] != garden["snapshot"]["id"]
    assert garden["snapshot"]["revenue"] == "36500000.00"


@pytest.mark.parametrize("who", ["no_company", "bank"])
def test_no_company_or_bank_user_is_404(who):
    user = make_bank_user() if who == "bank" else make_user("owner")
    response = as_user(user).get(PATH)
    assert response.status_code == 404
    assert_matches_contract(response, method="get", path=PATH)


def test_anonymous_is_401():
    response = APIClient().get(PATH)
    assert response.status_code == 401
    assert_matches_contract(response, method="get", path=PATH)
