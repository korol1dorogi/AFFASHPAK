import pytest
from django.db import DatabaseError
from rest_framework.test import APIClient

from apps.core.testing import assert_matches_contract


@pytest.mark.django_db
def test_health_ok_matches_contract():
    response = APIClient().get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "ok"}
    assert_matches_contract(response, method="get", path="/api/health")


@pytest.mark.django_db
def test_health_reports_unavailable_database(monkeypatch):
    def broken() -> None:
        raise DatabaseError("down")

    monkeypatch.setattr("apps.core.views.connection.ensure_connection", broken)

    response = APIClient().get("/api/health")

    assert response.status_code == 503
    assert response.json()["database"] == "unavailable"
    assert_matches_contract(response, method="get", path="/api/health")


def test_contract_violation_is_detected():
    class FakeResponse(dict):
        status_code = 200
        content = b'{"status": "fine"}'

    with pytest.raises(Exception):  # noqa: B017 - any validation error is fine here
        assert_matches_contract(
            FakeResponse({"Content-Type": "application/json"}), method="get", path="/api/health"
        )
