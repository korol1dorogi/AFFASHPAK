"""SQL injection and stored-XSS guards across the API (security review 21.10.2026).

The ORM parameterises every query and there is no raw SQL (ruff S608/S610/S611 keep it so);
these tests pin the behaviour on the inputs that reach the database. Stored text comes back
as JSON data: the API never renders HTML, the frontend escapes it (React, CSP on the stand).
"""

from urllib.parse import quote

import pytest
from rest_framework.test import APIClient

from apps.accounts.demo import seed
from apps.applications.models import Application
from apps.core.factories import make_bank_user, make_company, make_user
from apps.documents.names import attachment_filename

SQL = [
    "' OR '1'='1",
    "' OR 1=1--",
    "'; DROP TABLE applications_application;--",
    "%' OR '%'='",
    "1) UNION SELECT username, password FROM auth_user--",
]
XSS = '<img src=x onerror="alert(1)"><script>alert(2)</script>'
pytestmark = pytest.mark.django_db


@pytest.fixture
def bank():
    seed()
    owner = make_user("owner")
    company = make_company(members={owner: "signatory"}, name="ООО Ромашка (демо)")
    Application.objects.create(
        company=company,
        need_type="cash_gap",
        purpose="Демо",
        requested_amount="100000.00",
        term_months=6,
        status="manual_review",
        prefill_source="manual",
    )
    client = APIClient()
    client.force_login(make_bank_user())
    return client


@pytest.mark.parametrize("payload", SQL)
def test_login_cannot_be_bypassed(payload):
    response = APIClient().post(
        "/api/auth/login", {"username": payload, "password": payload}, format="json"
    )
    assert response.status_code == 401


@pytest.mark.parametrize("payload", SQL)
def test_queue_search_treats_sql_as_text(bank, payload):
    response = bank.get(f"/api/bank/applications?search={quote(payload, safe='')}")
    assert response.status_code == 200
    assert response.json()["count"] == 0
    assert Application.objects.count() == 1  # nothing dropped


@pytest.mark.parametrize("param", ["ordering", "status", "product_kind", "grade", "assignee"])
@pytest.mark.parametrize("payload", SQL)
def test_queue_filters_accept_only_known_values(bank, param, payload):
    response = bank.get(f"/api/bank/applications?{param}={quote(payload, safe='')}")
    assert response.status_code == 400
    assert response["Content-Type"].startswith("application/json")


@pytest.mark.parametrize("payload", SQL)
def test_registry_lookup_validates_the_inn(payload):
    client = APIClient()
    client.force_login(make_user("owner"))
    assert client.get(f"/api/company/lookup?inn={quote(payload, safe='')}").status_code == 400


def test_stored_markup_comes_back_as_json_text():
    owner = make_user("owner", full_name=XSS)
    make_company(members={owner: "signatory"})
    client = APIClient()
    client.force_login(owner)
    created = client.post(
        "/api/applications",
        {
            "need_type": "cash_gap",
            "purpose": XSS,
            "requested_amount": "300000.00",
            "term_months": 6,
            "collateral_description": XSS,
        },
        format="json",
    )
    assert created.status_code == 201
    detail = client.get(f"/api/applications/{created.json()['id']}")
    assert detail["Content-Type"].startswith("application/json")
    assert detail.json()["purpose"] == XSS  # unchanged data; escaping is the renderer's job
    me = client.get("/api/auth/me")
    assert me["Content-Type"].startswith("application/json") and me.json()["full_name"] == XSS


def test_download_name_has_no_markup_characters():
    name = attachment_filename(XSS + ".pdf", "application/pdf")
    assert name.endswith(".pdf")
    assert not set('<>"/\\') & set(name)
