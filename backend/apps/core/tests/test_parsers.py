import pytest
from rest_framework.test import APIClient

from apps.core.factories import make_user

# Python's json gives up on deep nesting with RecursionError, which DRF does not catch.
DEEP_JSON = '{"a":' * 100_000 + "1" + "}" * 100_000


@pytest.mark.django_db
def test_deeply_nested_json_is_400_not_500():
    """Red team (S8): ~600 KB of nested objects crashed any JSON endpoint with 500."""
    client = APIClient()
    client.force_login(make_user("demo-client"))

    response = client.post("/api/calculators/annuity", DEEP_JSON, content_type="application/json")

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "parse_error"


@pytest.mark.django_db
def test_ordinary_json_still_parses():
    client = APIClient()
    client.force_login(make_user("demo-client"))

    response = client.post(
        "/api/calculators/annuity",
        {"principal": "1000000.00", "annual_rate": "0.24", "term_months": 12},
        format="json",
    )

    assert response.status_code == 200
