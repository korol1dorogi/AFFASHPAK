"""Pipeline after the 21.10 review: personas, plain texts, gaps, failures, registry companies."""

import re
import uuid
from decimal import Decimal

import pytest
from rest_framework.test import APIClient

from apps.applications.models import Application, ApplicationStatus
from apps.business import registry
from apps.business.models import Company
from apps.core.factories import make_user
from apps.integrations.flags import set_failing
from apps.pipeline import runner
from apps.pipeline.runner import execute
from apps.pipeline.tests.test_personas import _application, _documents

RAW_DECIMAL = re.compile(r"\d+\.\d{2,4}")  # «900000.00», «0.2400», «1.2500» — never for a client
SOURCE_CODES = re.compile(r"\b(egrul|bki|bank_account|transparent_business)\b")


def _decision(application: Application):
    application.refresh_from_db()
    return application.decisions.get()


def _plain(text: str) -> str:
    return text.replace(" ", " ")  # rubles() groups digits with no-break spaces


def _texts(decision) -> list[str]:
    texts = [reason["message"] for reason in decision.reasons] + list(decision.improvements)
    return [_plain(text) for text in texts]


@pytest.mark.django_db
def test_persona_2_factoring_for_the_shipment(seeded):
    application = _application(
        "demo_retail_supplier",
        "factoring_basic",
        "4500000.00",
        2,
        need_type="receivable_delay",
        invoice_amount="5000000.00",
    )
    _documents(application, ("contract", "shipment_document"))
    execute(application.pk)
    decision = _decision(application)
    offer = application.offers.get()
    assert (decision.outcome, decision.grade) == ("offer", "B")
    assert (offer.product.code, offer.amount) == ("factoring_basic", Decimal("4500000.00"))
    assert "Сразу — 90% суммы отгрузки: 4 500 000 ₽" in _texts(decision)


@pytest.mark.django_db
def test_persona_4_grade_c_goes_to_an_officer(seeded):
    application = _application(
        "demo_furniture_maker",
        "investment_loan_basic",
        "8000000.00",
        36,
        need_type="capex",
        collateral_description="Фрезерный станок с ЧПУ (демо)",
    )
    _documents(application, ("bank_statement", "tax_return", "contract", "invoice"))
    execute(application.pk)
    decision = _decision(application)
    assert application.status == ApplicationStatus.MANUAL_REVIEW
    assert decision.outcome == "manual_review"
    assert (application.score.total, application.score.grade) == (65, "C")


@pytest.mark.django_db
def test_persona_5_is_declined_with_improvements(seeded):
    application = _application(
        "demo_dependent_supplier",
        "working_capital_loan_basic",
        "3000000.00",
        12,
        need_type="working_capital",
    )
    _documents(application, ("bank_statement", "tax_return"))
    execute(application.pk)
    decision = _decision(application)
    assert decision.outcome == "declined"
    assert (application.score.total, application.score.grade) == (47, "E")
    assert len(decision.improvements) == 4


@pytest.mark.django_db
def test_persona_8_explains_why_the_product_changed(seeded):
    application = _application(
        "demo_equipment_no_collateral",
        "investment_loan_basic",
        "12000000.00",
        36,
        need_type="capex",
    )
    _documents(application, ("bank_statement", "tax_return", "contract", "invoice"))
    execute(application.pk)
    decision = _decision(application)
    requirements = next(r for r in decision.reasons if r["metric"] == "product_requirements")
    assert requirements["passed"] is False
    assert requirements["message"] == (
        "Инвестиционный кредит требует залог; подходит лизинг оборудования и транспорта"
    )
    offer = application.offers.get()
    assert any(r["metric"] == "product_requirements" for r in offer.reasons)
    assert "При сроке 60 мес допустимо 15 768 379 ₽" in _texts(decision)


CASES = [
    ("demo_coffee_shop", "overdraft_basic", "900000.00", 12, "cash_gap", ()),
    (
        "demo_garden_store",
        "working_capital_loan_basic",
        "5300000.00",
        12,
        "working_capital",
        ("bank_statement", "tax_return"),
    ),
    (
        "demo_equipment_no_collateral",
        "investment_loan_basic",
        "12000000.00",
        36,
        "capex",
        ("bank_statement", "tax_return", "contract", "invoice"),
    ),
]


@pytest.mark.django_db
@pytest.mark.parametrize(("username", "product", "amount", "term", "need", "docs"), CASES)
def test_client_texts_have_no_raw_numbers(seeded, username, product, amount, term, need, docs):
    application = _application(username, product, amount, term, need_type=need)
    _documents(application, docs)
    execute(application.pk)
    decision = _decision(application)
    assert [text for text in _texts(decision) if RAW_DECIMAL.search(text)] == []
    history = list(application.events.values_list("message", flat=True))
    assert not any(SOURCE_CODES.search(message) for message in history)
    assert "Бюро кредитных историй: данные получены" in history


@pytest.mark.django_db
def test_gaps_ask_for_data_with_formatted_amounts(seeded):
    application = _application("demo_garden_store", "working_capital_loan_basic", "1000.00", 12)
    execute(application.pk)
    application.refresh_from_db()
    request = application.info_requests.get()
    assert application.status == ApplicationStatus.INFO_REQUESTED
    assert "requested_amount" in request.fields
    assert set(request.document_kinds) == {"bank_statement", "tax_return"}
    assert "Минимальная сумма по продукту — 300 000 ₽" in _plain(request.message)
    assert not RAW_DECIMAL.search(request.message)


@pytest.mark.django_db
def test_a_pipeline_error_hands_the_application_to_an_officer(seeded, monkeypatch):
    def broken(*args, **kwargs):
        raise RuntimeError("simulated bug")

    monkeypatch.setattr(runner, "decide", broken)
    application = _application("demo_coffee_shop", "overdraft_basic", "900000.00", 12)
    execute(application.pk)
    decision = _decision(application)
    assert application.status == ApplicationStatus.MANUAL_REVIEW
    assert decision.reasons[0]["metric"] == "automatic_check"


@pytest.mark.django_db
def test_submit_answers_200_even_if_the_pipeline_breaks(
    seeded, monkeypatch, settings, django_capture_on_commit_callbacks
):
    settings.DEMO_MODE = True
    monkeypatch.setattr(runner, "decide", lambda *args, **kwargs: 1 / 0)
    client = APIClient()
    client.post("/api/demo/login", {"persona": "coffee_shop"}, format="json")
    body = {
        "need_type": "cash_gap",
        "purpose": "Демо: зарплата до поступления оплаты",
        "requested_amount": "900000.00",
        "term_months": 12,
        "product_code": "overdraft_basic",
    }
    app_id = client.post("/api/applications", body, format="json").json()["id"]
    with django_capture_on_commit_callbacks(execute=True):  # the pipeline runs on commit
        response = client.post(
            f"/api/applications/{app_id}/submit", HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4())
        )
    assert response.status_code == 200
    assert client.get(f"/api/applications/{app_id}").json()["status"] == "manual_review"


@pytest.mark.django_db
def test_a_registry_company_is_not_declined_as_unknown(seeded):
    """The registry and the pipeline's sources share one dataset (was: С2 for every non-persona)."""
    taken = set(Company.objects.values_list("inn", flat=True))
    inn = next(
        inn
        for inn, record in registry._records().items()
        if inn not in taken and record["registry_status"] == "active"
    )
    owner = make_user("owner")
    client = APIClient()
    client.force_login(owner)
    assert client.post("/api/company", {"inn": inn}, format="json").status_code == 201
    application = _application("owner", "overdraft_basic", "300000.00", 6)
    execute(application.pk)
    decision = _decision(application)
    assert not any(r["metric"] == "egrul_found" for r in decision.reasons)
    assert application.checks.get(source="egrul").status in {"ok", "warning"}
    # No statement connected yet: an officer looks at it, and the client is told why.
    bank_account = next(r for r in decision.reasons if r["metric"] == "source_bank_account")
    assert bank_account["message"].startswith("Счёт не подключён")


@pytest.mark.django_db
def test_scenario_7_outage_switched_on_through_the_demo_api(seeded, settings):
    settings.DEMO_MODE = True
    bank = APIClient()
    bank.post("/api/demo/login", {"persona": "bank"}, format="json")
    flags = {"egrul": False, "transparent_business": False, "bki": True, "bank_account": False}
    assert bank.put("/api/demo/failures", flags, format="json").status_code == 200
    application = _application("demo_bki_outage", "overdraft_basic", "900000.00", 12)
    execute(application.pk)
    decision = _decision(application)
    assert application.status == ApplicationStatus.MANUAL_REVIEW
    bki = next(r for r in decision.reasons if r["metric"] == "source_bki")
    assert bki["message"].startswith("Бюро кредитных историй сейчас не отвечает")
    set_failing("bki", False)


@pytest.mark.django_db
def test_bank_queue_shows_the_offered_product(seeded):
    application = _application(
        "demo_equipment_no_collateral",
        "investment_loan_basic",
        "12000000.00",
        36,
        need_type="capex",
    )
    _documents(application, ("bank_statement", "tax_return", "contract", "invoice"))
    execute(application.pk)
    bank = APIClient()
    bank.force_login(make_user("manager", kind="bank"))
    items = bank.get("/api/bank/applications").json()["results"]
    row = next(item for item in items if item["id"] == application.pk)
    assert row["product_kind"] == "leasing"
