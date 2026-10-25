"""Pipeline after the 22.10 architecture audit: stop factors first, an officer's draft under П3."""

from decimal import Decimal

import pytest

from apps.applications.models import ApplicationStatus
from apps.integrations.flags import set_failing
from apps.pipeline.runner import execute
from apps.pipeline.tests.test_personas import _application


@pytest.mark.django_db
def test_a_stop_factor_declines_before_asking_for_documents(seeded):
    """Liquidation (С1) with no documents: a decline, not «загрузите документы» (§2)."""
    application = _application(
        "demo_liquidating_company",
        "factoring_basic",
        "500000.00",
        2,
        need_type="receivable_delay",
        invoice_amount="1000000.00",
    )

    execute(application.pk)

    application.refresh_from_db()
    assert application.status == ApplicationStatus.DECLINED
    assert not application.info_requests.exists()
    assert application.decisions.get().reasons[0]["metric"] == "registry_status"


@pytest.mark.django_db
def test_an_officer_gets_the_draft_amount_under_p3(seeded):
    """Scenario 7: the bureau is down → manual review, with the limit the data allows."""
    set_failing("bki", True)
    application = _application("demo_bki_outage", "overdraft_basic", "900000.00", 12)

    execute(application.pk)

    application.refresh_from_db()
    assert application.status == ApplicationStatus.MANUAL_REVIEW
    reasons = {reason["metric"]: reason for reason in application.decisions.get().reasons}
    assert Decimal(reasons["overdraft_limit"]["value"]) == Decimal("900000.00")
    assert reasons["overdraft_limit"]["passed"] is True


@pytest.mark.django_db
def test_documents_are_named_in_the_request(seeded):
    application = _application(
        "demo_retail_supplier",
        "factoring_basic",
        "4500000.00",
        2,
        need_type="receivable_delay",
        invoice_amount="5000000.00",
    )

    execute(application.pk)

    request = application.info_requests.get()
    assert request.fields == []
    assert set(request.document_kinds) == {"contract", "shipment_document"}
    assert "Не хватает документов: договор, документ отгрузки (УПД)" in request.message
