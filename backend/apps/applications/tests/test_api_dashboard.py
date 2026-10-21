"""Calculator, bank dashboard and demo reset: contract, access, numbers."""

from decimal import Decimal

import pytest
from rest_framework.test import APIClient

from apps.accounts.demo import seed
from apps.accounts.demo_queue import seed_queue
from apps.applications.models import Application
from apps.core.testing import assert_matches_contract
from apps.integrations import flags
from apps.notifications.models import Notification

pytestmark = pytest.mark.django_db


@pytest.fixture
def media(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    return tmp_path


def login(persona: str) -> APIClient:
    client = APIClient()
    assert client.post("/api/demo/login", {"persona": persona}, format="json").status_code == 200
    return client


@pytest.fixture
def demo(settings, media):
    settings.DEMO_MODE = True
    seed()


# ───────────────────────── calculator ─────────────────────────


def test_annuity_matches_credit_math_and_the_contract():
    body = {"principal": "1000000.00", "annual_rate": "0.24", "term_months": 12}
    response = APIClient().post("/api/calculators/annuity", body, format="json")
    assert response.status_code == 200
    assert_matches_contract(
        response, method="post", path="/api/calculators/annuity", request_body=body
    )
    result = response.json()
    assert result["payment"] == "94559.60"  # credit_math docstring
    assert len(result["schedule"]) == 12
    assert result["schedule"][-1]["balance"] == "0.00"
    assert Decimal(result["total_paid"]) - Decimal(result["overpayment"]) == Decimal("1000000.00")


@pytest.mark.parametrize(
    "body",
    [
        {"principal": "0", "annual_rate": "0.24", "term_months": 12},
        {"principal": "1000", "annual_rate": "-0.1", "term_months": 12},
        {"principal": "1000", "annual_rate": "0.24", "term_months": 0},
        {"principal": "abc", "annual_rate": "0.24", "term_months": 12},
    ],
)
def test_annuity_rejects_bad_input(body):
    response = APIClient().post("/api/calculators/annuity", body, format="json")
    assert response.status_code == 400
    assert_matches_contract(response, method="post", path="/api/calculators/annuity")


# ───────────────────────── dashboard ─────────────────────────


def test_dashboard_counts_the_seeded_queue(demo, django_capture_on_commit_callbacks):
    with django_capture_on_commit_callbacks(execute=True):
        seed_queue(12)
    response = login("bank").get("/api/bank/dashboard?days=30")
    assert response.status_code == 200
    assert_matches_contract(response, method="get", path="/api/bank/dashboard")
    body = response.json()
    funnel = {row["stage"]: row["count"] for row in body["funnel"]}
    assert body["total_applications"] == funnel["submitted"] == 12
    assert funnel["processing"] == 12  # every one went through the pipeline
    assert funnel["issued"] <= funnel["signed"] <= funnel["offer"] + funnel["manual_review"]
    assert 0 < Decimal(body["auto_decision_share"]) <= 1
    assert "processing" in body["avg_hours_in_status"]


def test_dashboard_without_applications_has_no_share(demo):
    body = login("bank").get("/api/bank/dashboard").json()
    assert body["total_applications"] == 0
    assert body["auto_decision_share"] is None


def test_dashboard_is_for_the_bank_only(demo):
    assert login("coffee_shop").get("/api/bank/dashboard").status_code == 403
    assert APIClient().get("/api/bank/dashboard").status_code == 401
    assert login("bank").get("/api/bank/dashboard?days=500").status_code == 400


# ───────────────────────── demo reset ─────────────────────────


def test_reset_returns_the_stand_to_the_seeded_state(demo, django_capture_on_commit_callbacks):
    with django_capture_on_commit_callbacks(execute=True):
        seed_queue(5)
    flags.set_failing("bki", True)
    bank = login("bank")
    with django_capture_on_commit_callbacks(execute=True):
        response = bank.post("/api/demo/reset")
    assert response.status_code == 204
    assert_matches_contract(response, method="post", path="/api/demo/reset")
    assert flags.current()["bki"] is False
    assert Application.objects.count() == 30  # the default demo queue, seeded again
    assert not Notification.objects.exclude(application__in=Application.objects.all()).exists()


def test_reset_is_for_the_bank_and_the_demo_stand_only(demo, settings):
    assert login("coffee_shop").post("/api/demo/reset").status_code == 403
    settings.DEMO_MODE = False
    assert APIClient().post("/api/demo/reset").status_code == 404
