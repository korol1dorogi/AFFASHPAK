"""Fix 6.2: an outage from the demo panel is over by itself after FAILURE_TTL."""

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.demo import seed
from apps.integrations import adapters, flags
from apps.integrations.breaker import breaker
from apps.integrations.models import DemoState
from apps.pipeline.runner import execute
from apps.pipeline.tests.test_personas import _application, _documents

INN = "000100000170"  # persona 1
pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _clean():
    breaker.reset()
    yield
    breaker.reset()
    flags.reset()


def _age(source: str, by) -> None:
    """Pretend the flag was turned on `by` ago (updated_at is auto_now, so write it directly)."""
    DemoState.objects.filter(source=source).update(updated_at=timezone.now() - by)


def test_a_fresh_outage_holds():
    flags.set_failing("bki", True)
    _age("bki", flags.FAILURE_TTL / 2)
    assert flags.current()["bki"] is True
    assert adapters.fetch_all(INN, has_account=True)["bki"]["status"] == "unavailable"


def test_an_outage_older_than_the_ttl_is_over_for_the_pipeline_and_the_panel():
    flags.set_failing("bki", True)
    _age("bki", flags.FAILURE_TTL + timezone.timedelta(seconds=1))
    assert flags.failing_sources() == set()
    assert flags.current()["bki"] is False
    assert adapters.fetch_all(INN, has_account=True)["bki"]["status"] == "ok"


def test_turning_it_on_again_starts_the_ttl_anew():
    flags.set_failing("bki", True)
    _age("bki", flags.FAILURE_TTL * 2)
    flags.set_failing("bki", True)
    assert flags.current()["bki"] is True


def test_the_demo_panel_shows_an_expired_outage_as_off(settings):
    settings.DEMO_MODE = True
    seed()
    bank = APIClient()
    bank.force_login(get_user_model().objects.get(username="demo_bank"))
    body = {source: source == "bki" for source in flags.SOURCES}  # the panel sends all four
    assert bank.put("/api/demo/failures", body, format="json").json()["bki"] is True
    _age("bki", flags.FAILURE_TTL * 2)
    assert bank.get("/api/demo/failures").json()["bki"] is False


def test_scenario_7_still_goes_to_an_officer_with_a_fresh_outage(settings):
    settings.DEMO_MODE = True
    seed()
    flags.set_failing("bki", True)
    application = _application("demo_coffee_shop", "overdraft_basic", "900000.00", 12)
    _documents(application, tuple(application.product.required_documents))
    execute(application.pk)
    application.refresh_from_db()
    assert application.status == "manual_review"
    assert application.checks.get(source="bki").status == "unavailable"
