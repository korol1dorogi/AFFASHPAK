"""L4: persona 1 auto-offer, persona 6 stop-factor decline, BKI outage → manual review."""

import uuid
from decimal import Decimal

import pytest
from django.core.files.base import ContentFile
from django.utils import timezone

from apps.accounts.demo import seed
from apps.applications.models import Application, ApplicationStatus, Score
from apps.business.models import Membership
from apps.documents.models import Document
from apps.integrations.flags import reset, set_failing
from apps.pipeline.runner import execute
from apps.products.models import Product

_PDF = b"%PDF-1.4\n"


@pytest.fixture
def seeded(db):
    seed()
    yield
    reset()


def _application(
    username: str,
    product_code: str,
    amount: str,
    term: int,
    *,
    need_type: str = "cash_gap",
    collateral_description: str | None = None,
    invoice_amount: str | None = None,
) -> Application:
    membership = Membership.objects.get(user__username=username)
    return Application.objects.create(
        company=membership.company,
        created_by=membership.user,
        need_type=need_type,
        purpose="Демо: деньги на кассовый разрыв до выручки",
        product=Product.objects.get(code=product_code),
        requested_amount=Decimal(amount),
        term_months=term,
        invoice_amount=None if invoice_amount is None else Decimal(invoice_amount),
        collateral_description=collateral_description,
        status=ApplicationStatus.SUBMITTED,
        submitted_at=timezone.now(),
        prefill_source="recommendation",
    )


def _documents(application: Application, kinds: tuple[str, ...]) -> None:
    for kind in kinds:
        Document.objects.create(
            application=application,
            kind=kind,
            original_name=f"{kind}.pdf",
            content_type="application/pdf",
            size=len(_PDF),
            sha256="ab" * 32,
            file=ContentFile(_PDF, name=f"{uuid.uuid4().hex}.pdf"),
        )


@pytest.mark.django_db
def test_persona_1_gets_an_automatic_overdraft_offer(seeded):
    application = _application("demo_coffee_shop", "overdraft_basic", "900000.00", 12)

    execute(application.pk)

    application.refresh_from_db()
    decision = application.decisions.get()
    offer = application.offers.get()
    assert application.status == ApplicationStatus.OFFER
    assert (application.score.total, application.score.grade) == (92, "A")
    assert decision.outcome == "offer"
    assert decision.decided_by == "auto"
    assert decision.grade == "A"
    assert offer.amount == Decimal("900000.00")
    assert offer.rate == Decimal("0.2000")
    assert offer.monthly_payment is None
    assert offer.is_counteroffer is False
    assert application.source_unavailable is False


@pytest.mark.django_db
def test_persona_6_is_declined_on_the_stop_factor_without_a_score(seeded):
    application = _application("demo_liquidating_company", "overdraft_basic", "500000.00", 6)

    execute(application.pk)

    application.refresh_from_db()
    decision = application.decisions.get()
    assert application.status == ApplicationStatus.DECLINED
    assert decision.outcome == "declined"
    assert decision.grade is None
    assert decision.reasons[0]["metric"] == "registry_status"
    assert not Score.objects.filter(application=application).exists()
    assert not application.checks.exists()


@pytest.mark.django_db
def test_bki_outage_sends_the_application_to_manual_review(seeded):
    set_failing("bki", True)
    application = _application("demo_bki_outage", "overdraft_basic", "900000.00", 12)

    execute(application.pk)

    application.refresh_from_db()
    decision = application.decisions.get()
    bki = application.checks.get(source="bki")
    assert application.status == ApplicationStatus.MANUAL_REVIEW
    assert application.source_unavailable is True
    assert bki.status == "unavailable"
    assert (application.score.total, application.score.grade) == (82, "B")
    assert decision.outcome == "manual_review"
    assert any(reason["metric"] == "source_bki" for reason in decision.reasons)


@pytest.mark.django_db
def test_persona_3_gets_a_dscr_counteroffer(seeded):
    application = _application(
        "demo_garden_store",
        "working_capital_loan_basic",
        "5300000.00",
        12,
        need_type="working_capital",
    )
    _documents(application, ("bank_statement", "tax_return"))

    execute(application.pk)

    application.refresh_from_db()
    offer = application.offers.get()
    assert application.status == ApplicationStatus.OFFER
    assert application.decisions.get().outcome == "counteroffer"
    assert offer.amount == Decimal("2009314.00")
    assert offer.rate == Decimal("0.2400")
    assert offer.is_counteroffer is True
    assert offer.product_changed is False
    assert offer.monthly_payment is not None


@pytest.mark.django_db
def test_persona_8_is_offered_leasing_instead_of_an_unsecured_loan(seeded):
    application = _application(
        "demo_equipment_no_collateral",
        "investment_loan_basic",
        "12000000.00",
        36,
        need_type="capex",
    )
    _documents(application, ("bank_statement", "tax_return", "contract", "invoice"))

    execute(application.pk)

    application.refresh_from_db()
    offer = application.offers.get()
    assert application.decisions.get().outcome == "alternative_product"
    assert offer.product.code == "leasing_basic"
    assert offer.amount == Decimal("11443551.00")
    assert offer.rate == Decimal("0.2250")
    assert offer.product_changed is True
    assert offer.is_counteroffer is True
