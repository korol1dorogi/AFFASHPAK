"""L2 migrations keep data written by the S3-era schema (stand runs auto-deploy)."""

from datetime import date
from decimal import Decimal

import pytest
from django.db import connection
from django.db.migrations.executor import MigrationExecutor

OLD = [
    ("business", "0001_initial"),
    ("applications", "0001_initial"),
    ("documents", "0001_initial"),
]
NEW = [
    ("business", "0003_alter_company_options_remove_company_owner_and_more"),
    ("applications", "0003_applicationevent_check_decision_disbursement_and_more"),
    ("documents", "0002_document_info_request_document_uploaded_by_and_more"),
]


def migrate(targets):
    executor = MigrationExecutor(connection)
    executor.loader.build_graph()
    executor.migrate(targets)
    return executor.loader.project_state(targets).apps


@pytest.mark.django_db(transaction=True)
def test_owner_becomes_signatory_and_old_statuses_go_to_manual_review():
    old = migrate(OLD)
    User = old.get_model("auth", "User")
    Business = old.get_model("business", "Business")
    Application = old.get_model("applications", "Application")
    owner = User.objects.create(username="legacy-owner")
    business = Business.objects.create(
        owner=owner,
        legal_form="ooo",
        name="ООО Наследие (демо)",
        inn="0099999999",
        ogrn="0000000000000",
        okved="56.10",
        registered_at=date(2020, 1, 1),
        region="00",
    )
    legacy = {
        status: Application.objects.create(
            business=business,
            need_type="cash_gap",
            purpose="демо",
            requested_amount=Decimal("1000.00"),
            term_months=1,
            status=status,
        ).pk
        for status in ("draft", "in_review", "approved")
    }

    new = migrate(NEW)
    Membership = new.get_model("business", "Membership")
    NewApplication = new.get_model("applications", "Application")

    membership = Membership.objects.get(user_id=owner.pk)
    assert membership.role == "signatory"
    assert membership.company_id == business.pk
    statuses = {
        old_status: NewApplication.objects.get(pk=pk).status for old_status, pk in legacy.items()
    }
    assert statuses == {
        "draft": "draft",
        "in_review": "manual_review",
        "approved": "manual_review",
    }
    assert NewApplication.objects.get(pk=legacy["draft"]).version == 0

    migrate(executor_latest())


def executor_latest():
    executor = MigrationExecutor(connection)
    return executor.loader.graph.leaf_nodes()
