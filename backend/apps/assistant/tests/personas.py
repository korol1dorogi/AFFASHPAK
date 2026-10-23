"""Persona applications for the assistant tool tests: the real pipeline, the scenarios' outcomes
(docs/demo.md): 1 offer (A), 3 DSCR counteroffer, 4 grade C → officer, 5 grade E decline,
6 stop factor (liquidation)."""

from apps.applications.models import Application
from apps.pipeline.runner import execute
from apps.pipeline.tests.test_personas import _application, _documents

PERSONAS = {
    1: ("demo_coffee_shop", "overdraft_basic", "900000.00", 12, {}, ()),
    3: (
        "demo_garden_store",
        "working_capital_loan_basic",
        "5300000.00",
        12,
        {"need_type": "working_capital"},
        ("bank_statement", "tax_return"),
    ),
    4: (
        "demo_furniture_maker",
        "investment_loan_basic",
        "8000000.00",
        36,
        {"need_type": "capex", "collateral_description": "Фрезерный станок с ЧПУ (демо)"},
        ("bank_statement", "tax_return", "contract", "invoice"),
    ),
    5: (
        "demo_dependent_supplier",
        "working_capital_loan_basic",
        "3000000.00",
        12,
        {"need_type": "working_capital"},
        ("bank_statement", "tax_return"),
    ),
    6: ("demo_liquidating_company", "overdraft_basic", "500000.00", 6, {}, ()),
}


def persona_application(number: int, *, run: bool = True) -> Application:
    username, product, amount, term, extra, documents = PERSONAS[number]
    application = _application(username, product, amount, term, **extra)
    _documents(application, documents)
    if run:
        execute(application.pk)
        application.refresh_from_db()
    return application
