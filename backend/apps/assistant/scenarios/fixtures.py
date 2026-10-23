"""Persona applications for the assistant scenarios (И4): `application: latest` gets one.

The same applications as the scenarios of docs/demo.md and the pipeline's persona tests, made
through the real pipeline, so the tools answer with the figures the jury sees. Runtime code (the
eval command runs on a stand too), so no test helpers are imported here.
"""

import uuid
from dataclasses import dataclass, field
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.utils import timezone

from apps.applications.models import BKI_CONSENT_VERSION, Application, ApplicationStatus, BkiConsent
from apps.business.models import Membership
from apps.demo_data.build import BANK_USERS
from apps.documents.models import Document
from apps.integrations import flags
from apps.pipeline.runner import execute
from apps.products.models import Product

PDF = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF\n"


@dataclass(frozen=True)
class Spec:
    product: str
    amount: str
    term: int
    need_type: str = "cash_gap"
    documents: tuple[str, ...] = ()
    invoice_amount: str | None = None
    collateral_description: str | None = None
    purpose: str = "Демо: сценарий ассистента"
    extra: dict = field(default_factory=dict)


# Persona code → the application of its scenario (docs/demo.md, «Персоны»).
SPECS: dict[str, Spec] = {
    "coffee_shop": Spec("overdraft_basic", "900000.00", 12),
    "retail_supplier": Spec(
        "factoring_basic", "4500000.00", 2, "receivable_delay",
        ("contract", "shipment_document"), invoice_amount="5000000.00",
    ),
    "garden_store": Spec(
        "working_capital_loan_basic", "5300000.00", 12, "working_capital",
        ("bank_statement", "tax_return"),
    ),
    "furniture_maker": Spec(
        "investment_loan_basic", "8000000.00", 36, "capex",
        ("bank_statement", "tax_return", "contract", "invoice"),
        collateral_description="Фрезерный станок с ЧПУ (демо)",
    ),
    "dependent_supplier": Spec(
        "working_capital_loan_basic", "3000000.00", 12, "working_capital",
        ("bank_statement", "tax_return"),
    ),
    "liquidating_company": Spec("overdraft_basic", "500000.00", 6),
    "bki_outage": Spec("overdraft_basic", "900000.00", 12),
    "equipment_no_collateral": Spec(
        "investment_loan_basic", "12000000.00", 36, "capex",
        ("bank_statement", "tax_return", "contract", "invoice"),
    ),
}  # fmt: skip
# Personas that act inside another persona's company.
SAME_COMPANY = {"accountant": "furniture_maker"}


def persona_user(code: str):
    """The client of a persona (`demo_<code>`) or, for «bank», the first bank user."""
    username = BANK_USERS[0] if code == "bank" else f"demo_{code}"
    return get_user_model().objects.get(username=username)


def persona_application(code: str, *, failing: tuple[str, ...] = ()) -> Application:
    """A submitted application of the persona, decided by the pipeline. `failing` sources are
    switched off only while it runs (the bank queue outage of scenario 7)."""
    owner = SAME_COMPANY.get(code, code)
    spec = SPECS[owner]
    membership = Membership.objects.select_related("company", "user").get(
        user__username=f"demo_{owner}"
    )
    application = Application.objects.create(
        company=membership.company,
        created_by=membership.user,
        need_type=spec.need_type,
        purpose=spec.purpose,
        product=Product.objects.get(code=spec.product),
        requested_amount=Decimal(spec.amount),
        term_months=spec.term,
        invoice_amount=None if spec.invoice_amount is None else Decimal(spec.invoice_amount),
        collateral_description=spec.collateral_description,
        status=ApplicationStatus.SUBMITTED,
        submitted_at=timezone.now(),
        prefill_source="manual",
    )
    BkiConsent.objects.create(
        application=application, user=membership.user, text_version=BKI_CONSENT_VERSION
    )
    for kind in spec.documents:
        Document.objects.create(
            application=application,
            uploaded_by=membership.user,
            kind=kind,
            original_name=f"{kind}_demo.pdf",
            content_type="application/pdf",
            size=len(PDF),
            sha256="0" * 64,
            file=ContentFile(PDF, name=f"{uuid.uuid4().hex}.pdf"),
        )
    for source in failing:
        flags.set_failing(source, True)
    try:
        execute(application.pk)
    finally:
        for source in failing:
            flags.set_failing(source, False)
    application.refresh_from_db()
    return application
