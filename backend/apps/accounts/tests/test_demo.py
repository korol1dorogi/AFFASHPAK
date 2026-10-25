"""Demo personas, quick sign-in and the seed (DEMO_MODE=1 only)."""

import pytest
from django.contrib.auth.models import User
from django.core.management import call_command
from rest_framework.test import APIClient

from apps.accounts.demo import persona_catalog, seed
from apps.business.models import Company, FinancialSnapshot, Membership
from apps.core.testing import assert_matches_contract
from apps.products.models import Product

pytestmark = pytest.mark.django_db


@pytest.fixture
def demo_on(settings):
    settings.DEMO_MODE = True


def test_seed_creates_personas_once_and_keeps_demo_edits():
    first = seed()
    assert first["companies"] == 8 and first["users"] == 12
    assert Membership.objects.count() == first["memberships"] > 0
    assert FinancialSnapshot.objects.count() == first["snapshots"] == 8
    assert all(company.is_demo and "демо" in company.name for company in Company.objects.all())

    company = Company.objects.get(inn=_persona_inn("coffee_shop"))
    company.name = "Переименовано на демо"
    company.save()
    assert seed() == {"products": 0, "companies": 0, "users": 0, "memberships": 0, "snapshots": 0}
    company.refresh_from_db()
    assert company.name == "Переименовано на демо"


CATALOG = {
    "overdraft_basic",
    "factoring_basic",
    "working_capital_loan_basic",
    "investment_loan_basic",
    "leasing_basic",
}


def test_seed_loads_the_catalog_once():
    assert seed()["products"] == 5
    assert set(Product.objects.values_list("code", flat=True)) == CATALOG
    Product.objects.filter(code="overdraft_basic").update(name="Изменено на демо")
    assert seed()["products"] == 0
    assert Product.objects.count() == 5
    assert Product.objects.get(code="overdraft_basic").name == "Изменено на демо"


def test_after_seed_the_coffee_shop_gets_offers(demo_on):
    call_command("seed_demo")
    call_command("seed_demo")  # a restart must not fail or duplicate
    assert Product.objects.count() == 5
    client = APIClient()
    client.post("/api/demo/login", {"persona": "coffee_shop"}, format="json")
    body = {"need_type": "cash_gap"}
    response = client.post("/api/recommendations", body, format="json")
    assert response.status_code == 200
    assert_matches_contract(response, method="post", path="/api/recommendations", request_body=body)
    offers = response.json()["offers"]
    assert offers and offers[0]["product"]["kind"] == "overdraft"


def test_persona_8_capex_without_collateral_gets_leasing_with_reasons(demo_on):
    """test-scenarios.md, scenario 8, step 2: the loan needs collateral, leasing fits the product.

    Ranking is D6's: the loan stays rank 1 and warns that it needs collateral; leasing as the
    only offer comes from the decision (rule П6, L4), not from the preliminary match.
    """
    seed()
    client = APIClient()
    client.post("/api/demo/login", {"persona": "equipment_no_collateral"}, format="json")
    body = {"need_type": "capex", "amount": "12000000.00", "term_months": 36}
    response = client.post("/api/recommendations", body, format="json")
    assert response.status_code == 200
    assert_matches_contract(response, method="post", path="/api/recommendations", request_body=body)
    loan, leasing = response.json()["offers"]
    assert (loan["product"]["code"], loan["rank"]) == ("investment_loan_basic", 1)
    requirements = next(r for r in loan["reasons"] if r["metric"] == "product_requirements")
    assert "Нужен залог" in requirements["message"]  # the match has no collateral input
    assert (leasing["product"]["code"], leasing["rank"]) == ("leasing_basic", 2)
    assert (leasing["amount"], leasing["monthly_payment"]) == ("11443551.00", "440000.00")
    for offer in (loan, leasing):
        cut = next(r for r in offer["reasons"] if r["metric"] == "max_loan_by_dscr")
        assert cut["passed"] is False and offer["fits"] is False


def test_demo_users_cannot_sign_in_with_a_password():
    seed()
    assert not User.objects.get(username="demo_coffee_shop").has_usable_password()


def test_seed_command_does_nothing_without_demo_mode(settings):
    settings.DEMO_MODE = False
    call_command("seed_demo")
    assert not User.objects.exists()
    call_command("seed_demo", "--force")
    assert User.objects.filter(username="demo_bank").exists()


def test_personas_list_only_seeded_users(demo_on):
    client = APIClient()
    assert client.get("/api/demo/personas").json() == []
    seed()
    response = client.get("/api/demo/personas")
    assert response.status_code == 200
    assert_matches_contract(response, method="get", path="/api/demo/personas")
    personas = {persona["code"]: persona for persona in response.json()}
    assert len(personas) == len(persona_catalog()) == 10  # 8 personas, an accountant, the bank
    assert personas["coffee_shop"]["scenario"] == 1
    assert personas["bank"]["kind"] == "bank"
    assert personas["accountant"]["username"] == "demo_accountant"


@pytest.mark.parametrize(
    ("code", "kind", "role"),
    [
        ("coffee_shop", "client", "signatory"),
        ("accountant", "client", "preparer"),
        ("bank", "bank", None),
    ],
)
def test_demo_login_signs_in_as_the_persona(demo_on, code, kind, role):
    seed()
    client = APIClient()
    body = {"persona": code}
    response = client.post("/api/demo/login", body, format="json")
    assert response.status_code == 200
    assert_matches_contract(response, method="post", path="/api/demo/login", request_body=body)
    me = response.json()
    assert (me["kind"], me["company_role"], me["is_demo"]) == (kind, role, True)
    assert client.get("/api/auth/me").json()["id"] == me["id"]


def test_demo_login_unknown_persona_is_404(demo_on):
    seed()
    response = APIClient().post("/api/demo/login", {"persona": "nobody"}, format="json")
    assert response.status_code == 404
    assert_matches_contract(response, method="post", path="/api/demo/login")


def test_demo_login_requires_csrf(demo_on):
    seed()
    client = APIClient(enforce_csrf_checks=True)
    response = client.post("/api/demo/login", {"persona": "coffee_shop"}, format="json")
    assert response.status_code == 403


@pytest.mark.parametrize(
    ("method", "path"), [("get", "/api/demo/personas"), ("post", "/api/demo/login")]
)
def test_demo_endpoints_do_not_exist_without_demo_mode(settings, method, path):
    settings.DEMO_MODE = False
    seed()
    response = getattr(APIClient(), method)(path, {"persona": "coffee_shop"}, format="json")
    assert response.status_code == 404


def _persona_inn(code: str) -> str:
    from apps.accounts.demo import persona_dataset

    data = persona_dataset()
    key = data["personas"][code]["company"]
    return next(company["inn"] for company in data["companies"] if company["_key"] == key)
