"""World of the recommendation tests: the D3 catalog, personas and edge cases of the generator.

Personas are seeded from the synthetic generator (apps/demo_data, S2) exactly as on the stand;
edge cases (data-spec §10) become a company with one snapshot. Nothing is typed in by hand.
"""

from datetime import date
from decimal import Decimal

import pytest
from django.contrib.auth.models import User
from django.core.management import call_command
from rest_framework.test import APIClient

from apps.accounts.demo import SNAPSHOT_NUMBERS, persona_dataset, seed
from apps.business.models import Company, FinancialSnapshot
from apps.core.factories import make_company

AS_OF = date(2026, 10, 1)  # meta.as_of of the generator: persona ages of D4 §8


@pytest.fixture
def catalog(db):
    call_command("loaddata", "products", verbosity=0)


@pytest.fixture
def personas(catalog):
    seed()


def persona_user(code: str) -> User:
    return User.objects.get(username=f"demo_{code}")


def persona_company(code: str) -> Company:
    return persona_user(code).memberships.get().company


def as_user(user: User) -> APIClient:
    client = APIClient()
    client.force_login(user)
    return client


def snapshot(company: Company, period: str = "2026-09", **values) -> FinancialSnapshot:
    return FinancialSnapshot.objects.create(company=company, period=period, source="demo", **values)


@pytest.fixture
def edge_company(catalog):
    """Company of an `edge_cases[]` record of the generator with its snapshot."""
    edges = {edge["code"]: edge for edge in persona_dataset()["edge_cases"]}

    def build(code: str) -> Company:
        edge = edges[code]
        record = edge["company"]
        company = make_company(
            legal_form=record["legal_form"],
            name=record["name"],
            registered_at=date.fromisoformat(record["registered_at"]),
            registry_status=record["registry_status"],
        )
        values = edge["snapshot"]
        numbers = {
            name: None if values[name] is None else Decimal(values[name])
            for name in SNAPSHOT_NUMBERS
        }
        snapshot(company, values["period"], **numbers)
        return company

    return build
