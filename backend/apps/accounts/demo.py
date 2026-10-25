"""Demo stand: personas for quick sign-in and the seed they need (DEMO_MODE=1 only).

Everything comes from the synthetic generator (apps/demo_data, S2) and is marked «демо».
Seeding only creates what is missing, so restarts keep what people changed during a demo;
/api/demo/reset (B7) returns the seeded companies to their starting state.
"""

import json
from datetime import date
from decimal import Decimal
from functools import cache
from pathlib import Path

from django.contrib.auth.models import User
from django.db import transaction

from apps.accounts.models import UserKind, UserProfile
from apps.business.models import (
    Company,
    CompanyIntegration,
    FinancialSnapshot,
    IntegrationSource,
    Membership,
)
from apps.demo_data.build import BANK_USERS, generate
from apps.demo_data.personas import PERSONAS
from apps.products.models import Product

PRODUCTS_FIXTURE = Path(__file__).resolve().parents[1] / "products" / "fixtures" / "products.json"

BANK_PERSONA = "bank"
BANK_TITLE = "Сотрудник банка (демо)"

COMPANY_FIELDS = (
    "legal_form",
    "name",
    "ogrn",
    "okved",
    "okved_name",
    "region",
    "address",
    "registry_status",
    "director_name",
)
SNAPSHOT_NUMBERS = (
    "cleaned_credit_turnover",
    "cfads",
    "debt_service",
    "revenue",
    "cogs",
    "ebitda",
    "debt",
    "cash",
    "receivables",
    "inventory",
    "payables",
    "counterparty_concentration",
    "revenue_trend",
)


@cache
def persona_dataset() -> dict:
    """Personas and bank users only: they never depend on the seed (data-spec.md §6.6)."""
    return generate(n_companies=0)


def persona_catalog() -> list[dict]:
    """Every persona sign-in the generator defines, seeded or not."""
    data = persona_dataset()
    users = {user["_key"]: user for user in data["users"]}
    companies = {company["_key"]: company for company in data["companies"]}
    positions = {(m["user"], m["company"]): m["position"] for m in data["memberships"]}
    catalog = []
    for spec in PERSONAS:
        persona = data["personas"][spec.code]
        company = companies[persona["company"]]
        for index, key in enumerate(persona["users"]):
            user = users[key]
            if index == 0:
                code, title = spec.code, company["name"]
            else:
                code = user["username"].removeprefix("demo_")
                title = f"{positions[(key, persona['company'])]}: {company['name']}"
            catalog.append(
                {
                    "code": code,
                    "title": title,
                    "username": user["username"],
                    "scenario": spec.number,
                    "kind": UserKind.CLIENT,
                }
            )
    catalog.append(
        {
            "code": BANK_PERSONA,
            "title": BANK_TITLE,
            "username": BANK_USERS[0],
            "scenario": 1,
            "kind": UserKind.BANK,
        }
    )
    return catalog


def available_personas() -> list[dict]:
    """Personas whose user exists in the database (seeded)."""
    catalog = persona_catalog()
    existing = set(
        User.objects.filter(
            username__in=[persona["username"] for persona in catalog], is_active=True
        ).values_list("username", flat=True)
    )
    return [persona for persona in catalog if persona["username"] in existing]


def _decimal(value: str | None) -> Decimal | None:
    return None if value is None else Decimal(value)


@transaction.atomic
def seed(n_companies: int = 0) -> dict[str, int]:
    """Create missing products, demo companies, users, memberships and snapshots.

    Returns counts created. The catalog comes first: without it /api/recommendations finds nothing.
    """
    data = persona_dataset() if n_companies == 0 else generate(n_companies=n_companies)
    created = {"products": seed_products()}
    created |= load_companies(data)
    return created


def load_companies(data: dict, keys: set[str] | None = None) -> dict[str, int]:
    """Companies of a generated dataset with their users, memberships and snapshots.

    keys: only these company `_key`s (and the people working there); None — all of them.
    """
    created = {"companies": 0, "users": 0, "memberships": 0, "snapshots": 0}
    wanted = [m for m in data["memberships"] if keys is None or m["company"] in keys]
    user_keys = {m["user"] for m in wanted}

    companies: dict[str, Company] = {}
    for record in data["companies"]:
        if keys is not None and record["_key"] not in keys:
            continue
        company, is_new = Company.objects.get_or_create(
            inn=record["inn"],
            defaults={
                **{field: record[field] for field in COMPANY_FIELDS},
                "registered_at": date.fromisoformat(record["registered_at"]),
                "is_demo": True,
            },
        )
        companies[record["_key"]] = company
        created["companies"] += is_new

    users: dict[str, User] = {}
    for record in data["users"]:
        if keys is not None and record["_key"] not in user_keys:
            continue
        user, is_new = User.objects.get_or_create(username=record["username"])
        if is_new:
            user.set_unusable_password()  # demo users sign in through /api/demo/login only
            user.save(update_fields=["password"])
            UserProfile.objects.create(user=user, **record["profile"])
        users[record["_key"]] = user
        created["users"] += is_new

    for record in wanted:
        _, is_new = Membership.objects.get_or_create(
            user=users[record["user"]],
            company=companies[record["company"]],
            defaults={"role": record["role"], "position": record["position"]},
        )
        created["memberships"] += is_new

    for record in data["financial_snapshots"]:
        if record["company"] not in companies:
            continue
        _, is_new = FinancialSnapshot.objects.get_or_create(
            company=companies[record["company"]],
            period=record["period"],
            source=record["source"],
            defaults={field: _decimal(record[field]) for field in SNAPSHOT_NUMBERS},
        )
        created["snapshots"] += is_new
        CompanyIntegration.objects.get_or_create(  # the statement came through the account
            company=companies[record["company"]], source=IntegrationSource.BANK_ACCOUNT
        )
    return created


def seed_products() -> int:
    """The catalog from docs/products.md (D3 fixture), matched by code; existing rows are kept."""
    records = json.loads(PRODUCTS_FIXTURE.read_text(encoding="utf-8"))
    created = 0
    for record in records:
        fields = dict(record["fields"])
        _, is_new = Product.objects.get_or_create(code=fields.pop("code"), defaults=fields)
        created += is_new
    return created


def seeded_company_inns() -> set[str]:
    """Companies the stand seeds itself: the personas and the demo queue.

    Not `is_demo`: a company someone connects by INN is demo too (its data come from the
    registry simulator), and a reset must not wipe what another visitor is doing in it.
    """
    from apps.accounts.demo_queue import queue_companies

    return {c["inn"] for c in persona_dataset()["companies"]} | {
        c["inn"] for c in queue_companies()
    }


def _delete_files(storage, names: list[str]) -> None:
    for name in names:
        storage.delete(name)


def reset_demo() -> dict[str, int]:
    """Seeded companies back to their starting state: their applications (with notifications and
    files) go, outages are off and the demo queue is seeded again. Applications of companies
    people connected themselves stay. Returns what was deleted."""
    from apps.accounts.demo_queue import seed_queue
    from apps.applications.models import Application
    from apps.documents.models import Document
    from apps.integrations import flags
    from apps.integrations.breaker import breaker
    from apps.notifications.models import Notification

    applications = Application.objects.filter(company__inn__in=seeded_company_inns())
    storage = Document._meta.get_field("file").storage
    with transaction.atomic():
        files = list(
            Document.objects.filter(application__in=applications)
            .exclude(file="")
            .values_list("file", flat=True)
        )
        deleted = {
            "applications": applications.count(),
            "notifications": Notification.objects.filter(application__in=applications).count(),
        }
        applications.delete()  # notifications and documents go with them (CASCADE)
        flags.reset()
        # Files only once the rows are gone for good: a rollback must not leave rows without files.
        transaction.on_commit(lambda: _delete_files(storage, files))
    breaker.reset()
    seed()
    seed_queue()
    return deleted
