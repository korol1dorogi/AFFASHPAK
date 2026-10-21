"""Sign-in limits with the production defaults (settings.THROTTLE_DEFAULTS, docs/deploy.md)."""

import pytest
from django.conf import settings
from rest_framework.test import APIClient
from rest_framework.throttling import SimpleRateThrottle

from apps.accounts.demo import seed

pytestmark = pytest.mark.django_db


@pytest.fixture
def production_rates(monkeypatch):
    """Dev compose raises the limits for e2e; these tests check the defaults the stand uses."""
    monkeypatch.setattr(SimpleRateThrottle, "THROTTLE_RATES", dict(settings.THROTTLE_DEFAULTS))


def test_a_jury_can_switch_demo_personas_from_one_ip(settings, production_rates):
    settings.DEMO_MODE = True
    seed()
    personas = ["coffee_shop", "garden_store", "bank", "furniture_maker", "accountant"]
    statuses = [  # anonymous each time, one IP — the worst case for the limit
        APIClient().post("/api/demo/login", {"persona": personas[i % 5]}, format="json").status_code
        for i in range(30)
    ]
    assert statuses == [200] * 30


def test_password_login_stays_strict(production_rates):
    client = APIClient()
    body = {"username": "nobody", "password": "wrong-password"}
    statuses = [client.post("/api/auth/login", body, format="json").status_code for _ in range(30)]
    assert statuses[:10] == [401] * 10
    assert set(statuses[10:]) == {429}


def test_demo_login_has_its_own_ceiling(settings, production_rates, monkeypatch):
    settings.DEMO_MODE = True
    seed()
    rates = {**settings.THROTTLE_DEFAULTS, "demo_login": "3/min"}
    monkeypatch.setattr(SimpleRateThrottle, "THROTTLE_RATES", rates)
    # A fresh anonymous client each time: the limit is per IP, as after logging out.
    statuses = [
        APIClient().post("/api/demo/login", {"persona": "coffee_shop"}, format="json").status_code
        for _ in range(4)
    ]
    assert statuses == [200, 200, 200, 429]
