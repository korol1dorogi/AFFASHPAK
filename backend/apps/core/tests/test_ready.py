"""GET /api/ready: database and applied migrations (openapi: getReadiness)."""

import pytest
from django.db import DatabaseError
from django.db.migrations.executor import MigrationExecutor
from rest_framework.test import APIClient

from apps.core.testing import assert_matches_contract

pytestmark = pytest.mark.django_db
PATH = "/api/ready"


def test_ready_when_the_database_is_up_and_migrated():
    response = APIClient().get(PATH)
    assert response.status_code == 200
    assert_matches_contract(response, method="get", path=PATH)
    assert response.json() == {
        "status": "ready",
        "components": {"database": "ok", "migrations": "ok"},
    }


def test_not_ready_with_unapplied_migrations(monkeypatch):
    monkeypatch.setattr(MigrationExecutor, "migration_plan", lambda self, targets: ["pending"])
    response = APIClient().get(PATH)
    assert response.status_code == 503
    assert_matches_contract(response, method="get", path=PATH)
    assert response.json()["components"]["migrations"] == "unavailable"


def test_not_ready_without_the_database(monkeypatch):
    def down():
        raise DatabaseError("down")

    monkeypatch.setattr("apps.core.views.connection.ensure_connection", down)
    response = APIClient().get(PATH)
    assert response.status_code == 503
    assert response.json() == {
        "status": "not_ready",
        "components": {"database": "unavailable", "migrations": "unavailable"},
    }
