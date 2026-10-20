"""Demo stand: personas for quick sign-in and the seed they need (DEMO_MODE=1 only).

Everything comes from the synthetic generator (apps/demo_data, S2) and is marked «демо».
Seeding only creates what is missing, so restarts keep what people changed during a demo;
a full reset is /api/demo/reset (B7).
"""

from datetime import date
from decimal import Decimal
from functools import cache

from django.contrib.auth.models import User
from django.db import transaction

from apps.accounts.models import UserKind, UserProfile
from apps.business.models import Company, FinancialSnapshot, Membership
from apps.demo_data.build import BANK_USERS, generate
from apps.demo_data.personas import PERSONAS

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
    """Create missing demo companies, users, memberships and snapshots. Returns counts created."""
    data = persona_dataset() if n_companies == 0 else generate(n_companies=n_companies)
    created = {"companies": 0, "users": 0, "memberships": 0, "snapshots": 0}

    companies: dict[str, Company] = {}
    for record in data["companies"]:
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
        user, is_new = User.objects.get_or_create(username=record["username"])
        if is_new:
            user.set_unusable_password()  # demo users sign in through /api/demo/login only
            user.save(update_fields=["password"])
            UserProfile.objects.create(user=user, **record["profile"])
        users[record["_key"]] = user
        created["users"] += is_new

    for record in data["memberships"]:
        _, is_new = Membership.objects.get_or_create(
            user=users[record["user"]],
            company=companies[record["company"]],
            defaults={"role": record["role"], "position": record["position"]},
        )
        created["memberships"] += is_new

    for record in data["financial_snapshots"]:
        _, is_new = FinancialSnapshot.objects.get_or_create(
            company=companies[record["company"]],
            period=record["period"],
            source=record["source"],
            defaults={field: _decimal(record[field]) for field in SNAPSHOT_NUMBERS},
        )
        created["snapshots"] += is_new
    return created
