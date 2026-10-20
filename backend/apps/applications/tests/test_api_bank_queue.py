"""Bank queue: contract, access, filters, ordering, paging, counters."""

from datetime import timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

from apps.applications.models import Score
from apps.core.factories import make_application, make_company, make_user
from apps.core.testing import assert_matches_contract

QUEUE = "/api/bank/applications"


@pytest.fixture
def queue(world):
    company = world["company"]
    other = make_company(members={make_user("cafe_owner"): "signatory"}, name="ИП Кофейня (демо)")
    now = timezone.now()
    apps = {
        "draft": make_application(company),
        "review": make_application(
            company,
            "manual_review",
            product=world["loan"],
            requested_amount=Decimal("5300000.00"),
            status_changed_at=now - timedelta(hours=30),
        ),
        "info": make_application(
            other,
            "info_requested",
            product=world["overdraft"],
            status_changed_at=now - timedelta(hours=2),
            assignee=world["bank"],
            source_unavailable=True,
        ),
        "offer": make_application(
            other, "offer", product=world["overdraft"], status_changed_at=now - timedelta(hours=5)
        ),
    }
    Score.objects.create(application=apps["review"], grade="C", total=55, model_version="demo")
    return {**world, "apps": apps, "other": other}


def ids(response) -> list[int]:
    return [item["id"] for item in response.json()["results"]]


def test_queue_matches_contract_and_skips_drafts(queue):
    response = queue["as_bank"].get(QUEUE)
    assert response.status_code == 200
    assert_matches_contract(response, method="get", path=QUEUE)
    body = response.json()
    apps = queue["apps"]
    assert ids(response) == [apps["review"].pk, apps["offer"].pk, apps["info"].pk]
    assert (body["count"], body["page"], body["page_size"]) == (3, 1, 20)
    assert body["counters"]["manual_review"] == 1
    assert body["counters"]["submitted"] == 0
    assert "draft" not in body["counters"]

    review = body["results"][0]
    assert review["company_name"] == queue["company"].name
    assert review["product_kind"] == "working_capital_loan"
    assert review["requested_amount"] == "5300000.00"
    assert review["grade"] == "C"
    assert review["hours_in_status"] == 30
    assert review["assignee"] is None
    info = body["results"][2]
    assert info["source_unavailable"] is True
    assert info["assignee"]["full_name"] == "Менеджер (демо)"


def test_clients_get_403_and_anonymous_401(queue):
    response = queue["as_signatory"].get(QUEUE)
    assert response.status_code == 403
    assert_matches_contract(response, method="get", path=QUEUE)
    from rest_framework.test import APIClient

    assert APIClient().get(QUEUE).status_code == 401


@pytest.mark.parametrize(
    ("query", "expected"),
    [
        ("status=offer&status=info_requested", ["offer", "info"]),
        ("product_kind=overdraft", ["offer", "info"]),
        ("grade=C", ["review"]),
        ("assignee=me", ["info"]),
        ("assignee=none", ["review", "offer"]),
        ("min_hours_in_status=4", ["review", "offer"]),
        ("search=Кофейня", ["offer", "info"]),
        ("ordering=-requested_amount", ["review", "info", "offer"]),
        ("ordering=-status_changed_at", ["info", "offer", "review"]),
    ],
)
def test_filters_and_ordering(queue, query, expected):
    response = queue["as_bank"].get(f"{QUEUE}?{query}")
    assert response.status_code == 200
    by_id = {app.pk: name for name, app in queue["apps"].items()}
    names = [by_id[pk] for pk in ids(response)]
    if "ordering" in query:
        assert names == expected
    else:
        assert sorted(names) == sorted(expected)


def test_search_by_inn(queue):
    response = queue["as_bank"].get(f"{QUEUE}?search={queue['other'].inn}")
    assert set(ids(response)) == {queue["apps"]["info"].pk, queue["apps"]["offer"].pk}


def test_counters_ignore_the_status_filter(queue):
    body = queue["as_bank"].get(f"{QUEUE}?status=offer").json()
    assert body["count"] == 1
    assert (body["counters"]["offer"], body["counters"]["manual_review"]) == (1, 1)


def test_paging(queue):
    body = queue["as_bank"].get(f"{QUEUE}?page=2&page_size=2").json()
    assert (body["count"], body["page"], body["page_size"]) == (3, 2, 2)
    assert len(body["results"]) == 1


@pytest.mark.parametrize(
    "query", ["status=nope", "page=0", "page_size=101", "assignee=someone", "ordering=id"]
)
def test_invalid_query_is_400(queue, query):
    assert queue["as_bank"].get(f"{QUEUE}?{query}").status_code == 400
