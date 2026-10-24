"""Recommendation service on the personas of D4 §8 and edge cases: amounts, rates, reasons, ranks.

Numbers are those of docs/decision-model.md §8, docs/knowledge/credit.md and docs/products.md.
The preliminary grade assumes a clean credit history (no checks before the application).
"""

from datetime import timedelta
from decimal import Decimal

import pytest

from apps.core.factories import make_company
from apps.products.models import Product
from apps.recommendations.service import RecommendationInput, recommend
from apps.recommendations.tests.conftest import AS_OF, persona_company, snapshot
from apps.scoring.texts import rubles

pytestmark = pytest.mark.django_db


def run(company, need_type: str, **request):
    return recommend(company, RecommendationInput(need_type, **request), on_date=AS_OF)


def reason(offer, metric: str):
    return next(r for r in offer.reasons if r.metric == metric)


def codes(result) -> list[str]:
    return [offer.product.code for offer in result.offers]


def test_cash_gap_persona_1_overdraft_900_000(personas):
    result = run(persona_company("coffee_shop"), "cash_gap")

    assert result.is_preliminary and result.stop_factors == ()
    assert codes(result) == ["overdraft_basic"]
    offer = result.offers[0]
    assert (offer.rank, offer.amount, offer.term_months) == (1, Decimal("900000.00"), 12)
    assert offer.rate == Decimal("0.2000")  # grade A
    assert offer.monthly_payment is None and offer.fits
    limit = reason(offer, "overdraft_limit")
    assert (limit.value, limit.passed) == (Decimal("900000.00"), True)
    assert reason(offer, "score_total").value == Decimal(92)


def test_receivable_delay_persona_2_factoring_4_500_000(personas):
    result = run(
        persona_company("retail_supplier"), "receivable_delay", invoice_amount=Decimal("5000000")
    )

    offer = result.offers[0]
    assert codes(result) == ["factoring_basic"]
    assert (offer.amount, offer.term_months, offer.rate) == (
        Decimal("4500000.00"), 2, Decimal("0.2250"),
    )  # fmt: skip
    assert offer.monthly_payment is None and offer.fits
    assert reason(offer, "factoring_advance").value == Decimal("4500000.00")
    commission = reason(offer, "factoring_commission")
    assert commission.value == Decimal("25000.00")
    assert commission.message == (
        f"Разовая комиссия: {rubles(Decimal(25000))}, это 0,5% от суммы отгрузки"
    )


def test_working_capital_persona_3_is_limited_by_dscr(personas):
    result = run(persona_company("garden_store"), "working_capital")

    offer = result.offers[0]
    assert codes(result) == ["working_capital_loan_basic"]
    assert (offer.amount, offer.term_months, offer.rate) == (
        Decimal("2009314.00"), 12, Decimal("0.2400"),
    )  # fmt: skip
    assert offer.monthly_payment == Decimal("189999.92")
    assert reason(offer, "working_capital_need").value == Decimal("5300000.00")
    assert reason(offer, "max_loan_by_dscr").value == Decimal("2009314.00")
    assert reason(offer, "dscr_after").value == Decimal("1.2500")
    assert offer.fits


def test_capex_persona_4_investment_loan_then_leasing(personas):
    result = run(persona_company("furniture_maker"), "capex")

    assert codes(result) == ["investment_loan_basic", "leasing_basic"]
    loan, leasing = result.offers
    assert [loan.rank, leasing.rank] == [1, 2]
    assert (loan.amount, loan.rate, loan.term_months) == (
        Decimal("11639118.00"), Decimal("0.2125"), 36,
    )  # fmt: skip
    assert (leasing.amount, leasing.rate, leasing.term_months) == (
        Decimal("11443551.00"), Decimal("0.2250"), 36,
    )  # fmt: skip
    assert leasing.monthly_payment == Decimal("440000.00")
    assert "Нужен залог" in reason(loan, "product_requirements").message
    assert loan.fits and leasing.fits


def test_capex_persona_8_asks_more_than_dscr_allows(edge_company):
    """Persona 8 = data of Г7 (D15): leasing 11 443 551 ₽ on 36 months at 22.5%."""
    result = run(edge_company("g7"), "capex", amount=Decimal("12000000.00"), term_months=36)

    loan, leasing = result.offers
    assert (leasing.amount, leasing.rate) == (Decimal("11443551.00"), Decimal("0.2250"))
    assert loan.amount == Decimal("11639118.00")
    for offer in (loan, leasing):
        cut = reason(offer, "max_loan_by_dscr")
        assert cut.threshold == Decimal("12000000.00") and not cut.passed
        assert not offer.fits


def test_amount_above_the_limit_is_cut_and_explained(personas):
    result = run(persona_company("garden_store"), "working_capital", amount=Decimal("5300000.00"))

    offer = result.offers[0]
    assert offer.amount == Decimal("2009314.00")
    cut = reason(offer, "max_loan_by_dscr")
    assert (cut.value, cut.threshold, cut.passed) == (
        Decimal("2009314.00"), Decimal("5300000.00"), False,
    )  # fmt: skip
    assert cut.message == (
        f"На 12 месяцев под 24% можно взять не больше {rubles(cut.value)}, "
        "чтобы после платежей оставался запас 25%"
    )
    assert not offer.fits and offer.rank == 1


def test_amount_within_the_limit_is_offered_as_asked(personas):
    offer = run(persona_company("coffee_shop"), "cash_gap", amount=Decimal("500000.00")).offers[0]

    assert offer.amount == Decimal("500000.00") and offer.fits


def test_amount_below_amount_min_does_not_fit(personas):
    offer = run(persona_company("coffee_shop"), "cash_gap", amount=Decimal("50000.00")).offers[0]

    minimum = reason(offer, "amount_min")
    assert (minimum.threshold, minimum.passed) == (Decimal("100000.00"), False)
    assert not offer.fits


def test_amount_max_caps_the_limit(personas):
    Product.objects.filter(code="overdraft_basic").update(amount_max=Decimal("600000.00"))

    offer = run(persona_company("coffee_shop"), "cash_gap").offers[0]

    assert offer.amount == Decimal("600000.00")
    assert reason(offer, "amount_max").passed and offer.fits


def test_term_outside_the_product_range_does_not_fit(personas):
    offer = run(persona_company("coffee_shop"), "cash_gap", term_months=24).offers[0]

    assert offer.term_months == 12
    assert reason(offer, "term_months").message == "Этот продукт выдают на срок от 1 до 12 месяцев"
    assert not offer.fits


def test_stop_factor_c1_persona_6(personas):
    result = run(persona_company("liquidating_company"), "cash_gap")

    assert result.offers == ()
    [stop] = result.stop_factors
    assert (stop.metric, stop.passed) == ("registry_status", False)
    assert "ликвидируется" in stop.message


def test_stop_factor_c5_business_younger_than_6_months(catalog):
    company = make_company(legal_form="ip", registered_at=AS_OF - timedelta(days=95))
    snapshot(company, cleaned_credit_turnover=Decimal("3000000.00"))

    result = run(company, "cash_gap")

    assert result.offers == ()
    [stop] = result.stop_factors
    assert (stop.metric, stop.value, stop.threshold) == ("business_age_months", 3, 6)


def test_stop_factor_c3_is_seen_from_the_snapshot(catalog):
    company = make_company()
    snapshot(company, ebitda=Decimal("-1.00"), debt=Decimal("100.00"))

    result = run(company, "cash_gap")

    assert result.offers == () and result.stop_factors[0].metric == "ebitda"


def test_young_business_gets_the_overdraft_alternative_first(edge_company):
    """e_young_wcl: the loan wants 12 months of business, 8 is enough for the overdraft (П6)."""
    result = run(edge_company("e_young_wcl"), "working_capital")

    assert codes(result) == ["overdraft_basic", "working_capital_loan_basic"]
    overdraft, loan = result.offers
    assert overdraft.fits and overdraft.amount == Decimal("912500.01")
    requirements = reason(loan, "product_requirements")
    assert not requirements.passed and "не меньше 1 года" in requirements.message
    assert loan.rank == 2 and not loan.fits


def test_product_that_cannot_be_sized_is_left_out(edge_company):
    """Г1: no free cash flow for a new payment — the loan is not offered, not offered at 0 ₽."""
    result = run(edge_company("g1"), "working_capital")

    assert codes(result) == ["overdraft_basic"]


def test_no_snapshot_no_offers(catalog):
    assert run(make_company(), "capex").offers == ()


def test_all_money_is_decimal(personas):
    for offer in run(persona_company("garden_store"), "working_capital").offers:
        for value in (offer.amount, offer.rate, offer.monthly_payment):
            assert isinstance(value, Decimal)
        for item in offer.reasons:
            assert item.value is None or isinstance(item.value, Decimal)
