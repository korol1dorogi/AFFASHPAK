from decimal import Decimal

import pytest
from rest_framework.test import APIClient

from apps.accounts.models import UserKind
from apps.core.factories import make_company, make_product, make_user


def client_for(user) -> APIClient:
    client = APIClient()
    client.force_login(user)
    return client


@pytest.fixture(autouse=True)
def _pipeline_off(settings):
    """These tests drive transitions themselves. The live pipeline is in apps/pipeline."""
    settings.PIPELINE_ENABLED = False


@pytest.fixture
def world(db):
    """A company with a signatory and a preparer, an outsider and a bank manager."""
    signatory = make_user("director", full_name="Анна Демо")
    preparer = make_user("accountant", full_name="Ольга Демо")
    outsider = make_user("outsider")
    bank = make_user("manager", kind=UserKind.BANK, full_name="Менеджер (демо)")
    company = make_company(members={signatory: "signatory", preparer: "preparer"})
    make_company(members={outsider: "signatory"}, name="ООО Чужая (демо)")
    overdraft = make_product()
    loan = make_product(
        "working_capital_demo",
        kind="working_capital_loan",
        name="КПО (демо)",
        is_revolving=False,
        term_max_months=36,
        rate_min=Decimal("0.20"),
        rate_max=Decimal("0.28"),
    )
    return {
        "company": company,
        "signatory": signatory,
        "preparer": preparer,
        "outsider": outsider,
        "bank": bank,
        "overdraft": overdraft,
        "loan": loan,
        "as_signatory": client_for(signatory),
        "as_preparer": client_for(preparer),
        "as_outsider": client_for(outsider),
        "as_bank": client_for(bank),
    }
