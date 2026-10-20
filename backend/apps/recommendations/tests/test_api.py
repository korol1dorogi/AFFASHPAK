"""POST /api/recommendations: contract, the four needs on personas, validation, access, scoping."""

from datetime import timedelta
from decimal import Decimal

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.core.factories import make_bank_user, make_company, make_user
from apps.core.testing import assert_matches_contract
from apps.recommendations.tests.conftest import as_user, persona_user, snapshot

pytestmark = pytest.mark.django_db
URL = "/api/recommendations"


def post(client: APIClient, body: dict):
    response = client.post(URL, body, format="json")
    assert_matches_contract(response, method="post", path=URL, request_body=body)
    return response


def recommend_as(code: str, body: dict) -> dict:
    response = post(as_user(persona_user(code)), body)
    assert response.status_code == 200, response.content
    return response.json()


def first(data: dict) -> dict:
    offer = data["offers"][0]
    assert offer["rank"] == 1
    return offer


def metrics(offer: dict) -> dict:
    return {reason["metric"]: reason for reason in offer["reasons"]}


def test_cash_gap_persona_1(personas):
    data = recommend_as("coffee_shop", {"need_type": "cash_gap"})

    assert data["is_preliminary"] is True and data["stop_factors"] == []
    offer = first(data)
    assert offer["product"]["code"] == "overdraft_basic"
    assert offer["amount"] == "900000.00" and offer["monthly_payment"] is None
    assert offer["fits"] is True
    assert metrics(offer)["overdraft_limit"]["value"] == "900000.00"


def test_receivable_delay_persona_2(personas):
    body = {"need_type": "receivable_delay", "invoice_amount": "5000000.00"}
    offer = first(recommend_as("retail_supplier", body))

    assert offer["product"]["code"] == "factoring_basic"
    assert (offer["amount"], offer["rate"]) == ("4500000.00", "0.2250")
    assert metrics(offer)["factoring_commission"]["value"] == "25000.00"


def test_working_capital_persona_3(personas):
    body = {"need_type": "working_capital", "amount": "5300000.00"}
    offer = first(recommend_as("garden_store", body))

    assert offer["product"]["code"] == "working_capital_loan_basic"
    assert (offer["amount"], offer["rate"], offer["term_months"]) == ("2009314.00", "0.2400", 12)
    assert offer["monthly_payment"] == "189999.92"
    cut = metrics(offer)["max_loan_by_dscr"]
    assert (cut["value"], cut["threshold"], cut["passed"]) == ("2009314.00", "5300000.00", False)
    assert offer["fits"] is False


def test_capex_persona_4(personas):
    data = recommend_as("furniture_maker", {"need_type": "capex"})

    assert [(o["rank"], o["product"]["code"], o["amount"]) for o in data["offers"]] == [
        (1, "investment_loan_basic", "11639118.00"),
        (2, "leasing_basic", "11443551.00"),
    ]


def test_stop_factor_persona_6(personas):
    data = recommend_as("liquidating_company", {"need_type": "cash_gap"})

    assert data["offers"] == []
    assert [stop["metric"] for stop in data["stop_factors"]] == ["registry_status"]


def test_stop_factor_c5_for_a_young_business(catalog):
    director = make_user("director")
    company = make_company(
        members={director: "signatory"},
        legal_form="ip",
        registered_at=timezone.localdate() - timedelta(days=95),
    )
    snapshot(company, cleaned_credit_turnover=Decimal("3000000.00"))

    data = post(as_user(director), {"need_type": "cash_gap"}).json()

    assert data["offers"] == []
    assert data["stop_factors"][0]["metric"] == "business_age_months"
    assert data["stop_factors"][0]["threshold"] == "6"


@pytest.mark.parametrize(
    ("body", "field"),
    [
        ({"need_type": "receivable_delay"}, "invoice_amount"),
        ({"need_type": "cash_gap", "purpose": "зарплата"}, "purpose"),
        ({"need_type": "cash_gap", "amount": "0.00"}, "amount"),
        ({"need_type": "cash_gap", "term_months": 0}, "term_months"),
        ({"need_type": "mortgage"}, "need_type"),
        ({}, "need_type"),
    ],
)
def test_invalid_input_is_400_with_the_field(personas, body, field):
    response = post(as_user(persona_user("coffee_shop")), body)

    assert response.status_code == 400
    assert field in response.json()["error"]["details"]


def test_anonymous_is_401(catalog):
    assert post(APIClient(), {"need_type": "cash_gap"}).status_code == 401


def test_bank_user_is_403(catalog):
    assert post(as_user(make_bank_user()), {"need_type": "cash_gap"}).status_code == 403


def test_client_without_company_is_404(catalog):
    assert post(as_user(make_user("lonely")), {"need_type": "cash_gap"}).status_code == 404


def test_only_the_users_own_company_is_used(catalog):
    alice, bob = make_user("alice"), make_user("bob")
    mine = make_company(members={alice: "signatory"})
    theirs = make_company(members={bob: "signatory"}, name="ООО Чужая (демо)")
    snapshot(mine, cleaned_credit_turnover=Decimal("1000000.00"))
    snapshot(theirs, cleaned_credit_turnover=Decimal("5000000.00"))

    for user, amount in ((alice, "300000.00"), (bob, "1500000.00")):
        data = post(as_user(user), {"need_type": "cash_gap"}).json()
        assert first(data)["amount"] == amount


def test_latest_snapshot_is_used(catalog):
    director = make_user("director")
    company = make_company(members={director: "signatory"})
    snapshot(company, "2026-08", cleaned_credit_turnover=Decimal("1000000.00"))
    snapshot(company, "2026-09", cleaned_credit_turnover=Decimal("2000000.00"))

    assert first(post(as_user(director), {"need_type": "cash_gap"}).json())["amount"] == (
        "600000.00"
    )


def test_csrf_is_enforced(personas):
    client = APIClient(enforce_csrf_checks=True)
    client.force_login(persona_user("coffee_shop"))

    assert post(client, {"need_type": "cash_gap"}).status_code == 403
