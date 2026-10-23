"""XP1: «что если» под оффером — payment, DSCR and the allowed amount for another term.

The counteroffer comes from the real pipeline (persona 3, scenario 3: 2 009 314 ₽ for 12 months),
and every expected number is computed with credit_math here, not typed in.
"""

from decimal import Decimal

import pytest

from apps.applications.models import ApplicationStatus
from apps.business.models import FinancialSnapshot
from apps.core.factories import make_application, make_bank_user
from apps.core.testing import assert_matches_contract
from apps.credit_math import annuity_payment, max_loan_by_dscr
from apps.integrations.breaker import breaker
from apps.integrations.flags import reset
from apps.pipeline.runner import execute
from apps.pipeline.tests.test_personas import _application, _documents
from apps.recommendations.service import latest_snapshot
from apps.recommendations.tests.conftest import as_user, persona_company, persona_user


def url(application) -> str:
    return f"/api/applications/{application.pk}/what-if"


def post(client, application, **body):
    return client.post(url(application), body, format="json")


@pytest.fixture(autouse=True)
def _fresh_sources():
    breaker.reset()
    yield
    breaker.reset()
    reset()


@pytest.fixture
def counteroffer(personas):
    """Persona 3 asks 5.3 mln for 12 months and gets the DSCR counteroffer (scenario 3)."""
    application = _application(
        "demo_garden_store",
        "working_capital_loan_basic",
        "5300000.00",
        12,
        need_type="working_capital",
    )
    _documents(application, ("bank_statement", "tax_return"))
    execute(application.pk)
    application.refresh_from_db()
    assert application.status == ApplicationStatus.OFFER
    return application


@pytest.fixture
def garden_store():
    return as_user(persona_user("garden_store"))


def dscr_limit(application, term: int) -> Decimal:
    """What credit_math allows for this term at the offer's rate — the number the UI shows."""
    offer = application.offers.get()
    snapshot = latest_snapshot(application.company)
    min_dscr = Decimal(str(offer.product.params["min_dscr"]))
    metric = max_loan_by_dscr(snapshot.cfads, snapshot.debt_service, offer.rate, term, min_dscr)
    return metric.value


@pytest.mark.django_db
def test_persona_3_on_18_months_gets_a_bigger_amount(counteroffer, garden_store):
    allowed = dscr_limit(counteroffer, 18)
    assert allowed == Decimal("2848485")  # scenario 3: more than 2 009 314 ₽ for 12 months

    response = post(garden_store, counteroffer, amount="2848485.00", term_months=18)

    assert response.status_code == 200
    body = response.json()
    assert Decimal(body["max_amount"]) == allowed
    assert body["rate"] == "0.2400"
    assert body["monthly_payment"] == str(
        annuity_payment(Decimal("2848485.00"), Decimal("0.24"), 18)
    )
    assert body["fits"] is True
    assert Decimal(body["dscr_after"]) >= Decimal(body["min_dscr"]) == Decimal("1.25")
    assert all(reason["passed"] for reason in body["reasons"])


@pytest.mark.django_db
def test_on_the_offer_term_the_limit_is_the_offer_itself(counteroffer, garden_store):
    offer = counteroffer.offers.get()
    body = post(garden_store, counteroffer, amount=str(offer.amount), term_months=12).json()
    assert Decimal(body["max_amount"]) == offer.amount == Decimal("2009314.00")
    assert body["monthly_payment"] == str(offer.monthly_payment)
    assert body["fits"] is True


@pytest.mark.django_db
def test_the_longest_term_of_the_product(counteroffer, garden_store):
    body = post(garden_store, counteroffer, amount="3000000.00", term_months=24).json()
    assert Decimal(body["max_amount"]) == dscr_limit(counteroffer, 24) == Decimal("3593645")
    assert body["fits"] is True


@pytest.mark.django_db
def test_more_than_the_cash_flow_carries_does_not_fit(counteroffer, garden_store):
    body = post(garden_store, counteroffer, amount="3000000.00", term_months=18).json()
    assert body["fits"] is False
    failed = {reason["metric"] for reason in body["reasons"] if not reason["passed"]}
    assert failed == {"max_loan_by_dscr", "dscr_after"}
    assert Decimal(body["dscr_after"]) < Decimal(body["min_dscr"])


@pytest.mark.django_db
def test_below_the_product_minimum_is_a_reason_not_an_error(counteroffer, garden_store):
    response = post(garden_store, counteroffer, amount="100000.00", term_months=12)
    assert response.status_code == 200
    body = response.json()
    assert body["fits"] is False
    reason = next(r for r in body["reasons"] if r["metric"] == "amount_min")
    assert (reason["value"], reason["threshold"], reason["passed"]) == (
        "100000.00",
        "300000.00",
        False,
    )


@pytest.mark.django_db
def test_without_cash_flow_the_limit_is_null_with_the_reason(counteroffer, garden_store):
    FinancialSnapshot.objects.filter(company=counteroffer.company).update(cfads=None)
    body = post(garden_store, counteroffer, amount="2009314.00", term_months=12).json()
    assert (body["max_amount"], body["dscr_after"], body["fits"]) == (None, None, False)
    assert body["reasons"][0]["metric"] == "max_loan_by_dscr"
    assert body["reasons"][0]["value"] is None
    assert body["reasons"][0]["message"]  # «нет данных», never 0


@pytest.mark.django_db
@pytest.mark.parametrize("term", [2, 25])
def test_a_term_outside_the_product_is_400(counteroffer, garden_store, term):
    response = post(garden_store, counteroffer, amount="2009314.00", term_months=term)
    assert response.status_code == 400
    assert response.json()["error"]["details"]["term_months"] == [
        "Срок по продукту — от 3 до 24 мес"
    ]


@pytest.mark.django_db
@pytest.mark.parametrize(
    "body",
    [
        {"amount": "0.00", "term_months": 12},
        {"amount": "2009314.00"},
        {"amount": "2009314.00", "term_months": 12, "rate": "0.10"},
    ],
)
def test_bad_input_is_400(counteroffer, garden_store, body):
    assert garden_store.post(url(counteroffer), body, format="json").status_code == 400


@pytest.mark.django_db
def test_another_company_gets_404(counteroffer):
    other = as_user(persona_user("coffee_shop"))
    assert post(other, counteroffer, amount="2009314.00", term_months=12).status_code == 404


@pytest.mark.django_db
def test_a_bank_user_gets_404(counteroffer):
    bank = as_user(make_bank_user())
    assert post(bank, counteroffer, amount="2009314.00", term_months=12).status_code == 404


@pytest.mark.django_db
def test_no_active_offer_is_409(personas, garden_store):
    draft = make_application(persona_company("garden_store"))
    response = post(garden_store, draft, amount="2009314.00", term_months=12)
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "no_active_offer"


@pytest.mark.django_db
def test_a_revolving_offer_is_409(personas):
    application = _application("demo_coffee_shop", "overdraft_basic", "900000.00", 12)
    _documents(application, tuple(application.product.required_documents))
    execute(application.pk)
    response = post(
        as_user(persona_user("coffee_shop")), application, amount="900000.00", term_months=12
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "revolving_product"


@pytest.mark.django_db
def test_the_answer_matches_the_contract(counteroffer, garden_store):
    body = {"amount": "2848485.00", "term_months": 18}
    response = garden_store.post(url(counteroffer), body, format="json")
    assert_matches_contract(response, method="post", path=url(counteroffer), request_body=body)
