"""Test data factories shared by every app. Synthetic, marked «демо», no real people.

Usage in tests:
    director = make_user("director")
    company = make_company(members={director: "signatory"})
    application = make_application(company, status="manual_review")
"""

import itertools
from datetime import date
from decimal import Decimal

from django.contrib.auth.models import User

from apps.accounts.models import UserKind, UserProfile
from apps.applications.models import Application, ApplicationStatus
from apps.business.models import Company, LegalForm, Membership
from apps.products.models import Product, ProductKind

_inn = itertools.count(1)


def make_user(username: str, *, kind: str = UserKind.CLIENT, full_name: str = "") -> User:
    user = User.objects.create_user(username, password="demo-password-123")
    UserProfile.objects.create(
        user=user, kind=kind, full_name=full_name or f"{username} (демо)", is_demo=True
    )
    return user


def make_bank_user(username: str = "bank") -> User:
    return make_user(username, kind=UserKind.BANK, full_name="Менеджер банка (демо)")


def make_company(*, members: dict[User, str] | None = None, **fields) -> Company:
    defaults = {
        "legal_form": LegalForm.OOO,
        "name": "ООО Ромашка (демо)",
        "inn": f"00{next(_inn):08d}",
        "ogrn": "0000000000000",
        "okved": "56.10",
        "registered_at": date(2020, 1, 15),
        "region": "00",
        "is_demo": True,
    }
    company = Company.objects.create(**{**defaults, **fields})
    for user, role in (members or {}).items():
        Membership.objects.create(user=user, company=company, role=role, position="Демо")
    return company


def make_product(code: str = "overdraft_demo", **fields) -> Product:
    defaults = {
        "kind": ProductKind.OVERDRAFT,
        "name": "Овердрафт (демо)",
        "rate_min": Decimal("0.18"),
        "rate_max": Decimal("0.26"),
        "term_min_months": 1,
        "term_max_months": 12,
        "amount_min": Decimal("100000"),
        "amount_max": Decimal("10000000"),
        "is_revolving": True,
        "params": {"alpha": "0.3"},
    }
    return Product.objects.create(code=code, **{**defaults, **fields})


def make_application(
    company: Company, status: str = ApplicationStatus.DRAFT, **fields
) -> Application:
    defaults = {
        "need_type": "cash_gap",
        "purpose": "Демо: кассовый разрыв",
        "requested_amount": Decimal("100000.00"),
        "term_months": 12,
        "prefill_source": "manual",
    }
    if "product" not in fields and "product_id" not in fields:
        # Complete by default: submit checks the product and its limits (completeness.py).
        defaults["product"] = (
            Product.objects.filter(code="overdraft_demo").first() or make_product()
        )
    return Application.objects.create(company=company, status=status, **{**defaults, **fields})
