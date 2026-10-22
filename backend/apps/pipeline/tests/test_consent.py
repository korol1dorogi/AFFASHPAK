"""SRC1: without the client's consent the pipeline never asks the credit bureau (218-FZ)."""

import pytest

from apps.applications.models import BkiConsent, Check
from apps.integrations import adapters
from apps.pipeline.runner import execute
from apps.pipeline.tests.test_personas import _application, _documents


@pytest.fixture
def asked(monkeypatch):
    """Sources the pipeline actually called."""
    calls: list[str] = []
    real = adapters._answer

    def spy(source, inn, *, has_account):
        calls.append(source)
        return real(source, inn, has_account=has_account)

    monkeypatch.setattr(adapters, "_answer", spy)
    return calls


@pytest.mark.django_db
def test_the_bureau_is_asked_with_the_consent(seeded, asked):
    application = _application("demo_coffee_shop", "overdraft_basic", "900000.00", 12)
    _documents(application, tuple(application.product.required_documents))
    execute(application.pk)
    assert "bki" in asked
    assert Check.objects.get(application=application, source="bki").status == "ok"


@pytest.mark.django_db
def test_no_consent_no_bureau_request(seeded, asked):
    application = _application("demo_coffee_shop", "overdraft_basic", "900000.00", 12)
    _documents(application, tuple(application.product.required_documents))
    BkiConsent.objects.filter(application=application).delete()  # e.g. an application from before

    execute(application.pk)

    assert "bki" not in asked
    assert {"egrul", "transparent_business"} <= set(asked)
    check = Check.objects.get(application=application, source="bki")
    assert check.status == "unavailable"
    assert check.data == {"consent_missing": True}
    assert check.summary == "Бюро кредитных историй: не запрашивали — нет согласия клиента"
    application.refresh_from_db()
    assert application.status == "manual_review"  # no data is not a decline
    texts = [reason["message"] for reason in application.decisions.get().reasons]
    assert any("Нет согласия на запрос в бюро" in text for text in texts)
