"""A living bank queue on a fresh stand: applications of the synthetic population.

Personas stay untouched (the jury runs their scenarios). Population companies — from the same
dataset the simulators answer from — each send one application, and the real pipeline decides:
offers, counteroffers, other products, manual review, info requests, declines. Some offers go on
to signing and disbursement; time in status is spread so the queue has fresh and overdue rows.
Deterministic (by position) and seeded once: rows marked QUEUE_MARK exist → nothing to do.
"""

import uuid
from datetime import timedelta
from decimal import ROUND_HALF_UP, Decimal

from django.core.files.base import ContentFile
from django.db.models import F

from apps.accounts.demo import load_companies
from apps.applications import services
from apps.applications.access import Actor
from apps.applications.models import (
    BKI_CONSENT_VERSION,
    ActorKind,
    Application,
    ApplicationEvent,
    ApplicationStatus,
)
from apps.business.models import Company, FinancialSnapshot, MemberRole, Membership
from apps.credit_math import factoring_advance, overdraft_limit
from apps.documents.models import Document
from apps.integrations.simulator_data import dataset
from apps.pipeline.runner import execute
from apps.products.models import Product

QUEUE_MARK = "(демо-очередь)"
DEFAULT_SIZE = 30
# Requested product by position: every kind shows up; the pipeline may still change it.
PLAN = (
    ("overdraft_basic", "cash_gap", "Зарплата и аренда до поступлений от покупателей"),
    ("working_capital_loan_basic", "working_capital", "Закупка товара к сезону"),
    ("factoring_basic", "receivable_delay", "Покупатель платит через 60 дней после отгрузки"),
    ("investment_loan_basic", "capex", "Новое оборудование для цеха"),
    ("leasing_basic", "capex", "Грузовой автомобиль для доставки"),
)
NO_DOCUMENTS_EVERY = 7  # one in seven forgets the documents → the pipeline asks for them
ISSUE_EVERY = 3  # one offer in three is accepted, signed and issued
PDF = b"%PDF-1.4\n1 0 obj\n<<>>\ntrailer\n%%EOF"


def queue_companies(size: int = DEFAULT_SIZE) -> list[dict]:
    """Population companies of the demo queue: the first `size`, the same ones on every stand."""
    data = dataset()
    return [c for c in data["companies"] if c["_key"] in data["_latent"]][:size]


def seed_queue(size: int = DEFAULT_SIZE) -> int:
    """Create the demo queue once; returns how many applications were created."""
    if Application.objects.filter(purpose__endswith=QUEUE_MARK).exists():
        return 0
    data = dataset()
    population = queue_companies(size)
    load_companies(data, {c["_key"] for c in population})
    created = 0
    for index, record in enumerate(population):
        company = Company.objects.get(inn=record["inn"])
        signatory = (
            Membership.objects.filter(company=company, role=MemberRole.SIGNATORY)
            .select_related("user")
            .first()
        )
        if signatory is None:
            continue
        application = _apply(index, company, signatory.user)
        # Through the state machine, like a client: consent, submit event, notifications.
        services.submit(application, _actor(signatory), consent_version=BKI_CONSENT_VERSION)
        execute(application.pk)
        application.refresh_from_db()
        if application.status == ApplicationStatus.OFFER and index % ISSUE_EVERY == 0:
            _issue(application, signatory)
        # Age the whole application by the same shift, journal included: the card's history,
        # the queue's hours in status / SLA and the dashboard then tell one story.
        shift = timedelta(hours=(index * 7) % 61)  # 0…60 h: some rows are past the norm
        Application.objects.filter(pk=application.pk).update(
            status_changed_at=F("status_changed_at") - shift,
            submitted_at=F("submitted_at") - shift,
            created_at=F("created_at") - shift - timedelta(hours=1),  # drafted before sending
        )
        ApplicationEvent.objects.filter(application=application).update(
            created_at=F("created_at") - shift
        )
        created += 1
    return created


def _apply(index: int, company: Company, user) -> Application:
    code, need, purpose = PLAN[index % len(PLAN)]
    product = Product.objects.get(code=code)
    snapshot = FinancialSnapshot.objects.filter(company=company).first()
    amount, invoice = _amounts(index, product, snapshot)
    application = Application.objects.create(
        company=company,
        created_by=user,
        need_type=need,
        purpose=f"{purpose} {QUEUE_MARK}",
        product=product,
        requested_amount=amount,
        term_months=min(max(12, product.term_min_months), product.term_max_months),
        invoice_amount=invoice,
        collateral_description=(
            "Приобретаемое оборудование (демо)"
            if code == "investment_loan_basic" and index % 2
            else None
        ),
        prefill_source="manual",
    )
    if index % NO_DOCUMENTS_EVERY != 3:
        for kind in product.required_documents:
            Document.objects.create(
                application=application,
                uploaded_by=user,
                kind=kind,
                original_name=f"{kind}_demo.pdf",
                content_type="application/pdf",
                size=len(PDF),
                sha256="0" * 64,
                file=ContentFile(PDF, name=f"{uuid.uuid4().hex}.pdf"),
            )
    return application


def _amounts(index: int, product: Product, snapshot) -> tuple[Decimal, Decimal | None]:
    """A plausible request from the company's own figures; every third one asks for more."""
    turnover = (snapshot and snapshot.cleaned_credit_turnover) or Decimal(1_000_000)
    cfads = (snapshot and snapshot.cfads) or Decimal(100_000)
    stretch = Decimal("1.6") if index % 3 == 1 else Decimal(1)
    invoice = None
    if product.kind == "overdraft":
        raw = overdraft_limit(turnover, Decimal(product.params["alpha"])) * stretch
    elif product.kind == "factoring":
        invoice = _round(turnover * Decimal("0.6"))
        raw = factoring_advance(invoice, Decimal(product.params["beta"])) * stretch
    elif product.kind == "working_capital_loan":
        raw = cfads * 8 * stretch
    else:
        raw = cfads * 20 * stretch
    amount = min(max(_round(raw), product.amount_min), product.amount_max)
    return amount, invoice


def _round(value: Decimal) -> Decimal:
    return (value / 10_000).quantize(Decimal(1), rounding=ROUND_HALF_UP) * 10_000


def _actor(membership: Membership) -> Actor:
    return Actor(kind=ActorKind.CLIENT, user=membership.user, role=membership.role)


def _issue(application: Application, membership: Membership) -> None:
    actor = _actor(membership)
    services.accept_offer(application, actor)
    application.refresh_from_db()
    _signature, code = services.start_signature(application, actor)
    services.confirm_signature(application, actor, code)  # disbursement follows on commit
