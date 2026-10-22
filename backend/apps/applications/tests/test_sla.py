"""Bank queue SLA (XP4): norms by status, the overdue boundary, the queue filter, the dashboard.

The clock is fixed: views read `timezone.now()` once per request and the tests patch it, so the
±1 second boundaries are exact and nothing sleeps.
"""

from datetime import UTC, datetime, timedelta

import pytest
from django.utils import timezone

from apps.applications.models import ApplicationStatus
from apps.applications.sla import DEFAULT_SLA_HOURS, sla_hours, sla_state
from apps.core.factories import make_application
from apps.core.testing import assert_matches_contract

S = ApplicationStatus
NOW = datetime(2026, 10, 22, 12, 0, tzinfo=UTC)
SECOND = timedelta(seconds=1)


@pytest.fixture(autouse=True)
def _fresh_warnings():
    """sla.py warns once per problem set; every test starts with a clean slate."""
    from apps.applications.sla import _warn

    _warn.cache_clear()


@pytest.fixture
def clock(monkeypatch):
    monkeypatch.setattr(timezone, "now", lambda: NOW)
    return NOW


def entered(hours: float, delta: timedelta = timedelta(0)) -> datetime:
    """When the status was entered so that `hours` (+ delta) have passed by NOW."""
    return NOW - timedelta(hours=hours) - delta


# ───────────────────────── norms and the boundary ─────────────────────────


def test_default_norms_only_where_the_bank_acts():
    assert sla_hours() == {"submitted": 1, "processing": 1, "manual_review": 24, "signed": 1}


@pytest.mark.parametrize(
    ("delta", "overdue", "hours"),
    [
        (-SECOND, False, 0),  # a second before the due time
        (timedelta(0), False, 0),  # exactly at the due time: not yet
        (SECOND, True, 0),  # a second after: overdue, less than an hour
        (timedelta(hours=2, minutes=30), True, 2),
    ],
)
def test_manual_review_boundary(delta, overdue, hours):
    state = sla_state(S.MANUAL_REVIEW, entered(24, delta), NOW)

    assert state.due_at == entered(24, delta) + timedelta(hours=24)
    assert (state.is_overdue, state.overdue_hours) == (overdue, hours)


@pytest.mark.parametrize(
    "status",
    [S.INFO_REQUESTED, S.OFFER, S.SIGNING, S.ISSUED, S.DECLINED, S.CANCELLED, S.DRAFT],
)
def test_client_and_final_statuses_never_become_overdue(status):
    state = sla_state(status, NOW - timedelta(days=30), NOW)

    assert (state.due_at, state.is_overdue, state.overdue_hours) == (None, False, 0)


def test_settings_override_a_norm(settings):
    settings.APPLICATION_SLA_HOURS = "manual_review=8"

    assert sla_hours()["manual_review"] == 8
    assert sla_state(S.MANUAL_REVIEW, entered(8, SECOND), NOW).is_overdue


@pytest.mark.parametrize(
    "raw",
    [
        "manual_review=abc",  # not a number
        "manual_review",  # no value
        "manual_review=-3",  # negative
        "manual_review=0",  # zero
        "foo=5",  # unknown status
        "offer=4",  # the client's turn: no norm by design
        "=5",
    ],
)
def test_broken_sla_hours_keeps_the_defaults_and_warns(settings, caplog, raw):
    """Red team of XP4: a typo in env SLA_HOURS crashed the start or answered 500."""
    settings.APPLICATION_SLA_HOURS = raw

    assert sla_hours() == {"submitted": 1, "processing": 1, "manual_review": 24, "signed": 1}
    assert "SLA_HOURS" in caplog.text


def test_valid_items_apply_next_to_broken_ones(settings):
    settings.APPLICATION_SLA_HOURS = " manual_review = 8 , foo=5, signed=2"

    assert sla_hours() == {"submitted": 1, "processing": 1, "manual_review": 8, "signed": 2}


def test_empty_sla_hours_is_the_defaults(settings):
    settings.APPLICATION_SLA_HOURS = ""

    assert sla_hours() == {"submitted": 1, "processing": 1, "manual_review": 24, "signed": 1}


def test_broken_sla_hours_is_a_system_check_warning(settings):
    from apps.applications.sla import check_sla_hours

    settings.APPLICATION_SLA_HOURS = "manual_review=abc"
    [warning] = check_sla_hours(None)
    assert warning.id == "applications.W001" and "manual_review=abc" in warning.msg

    settings.APPLICATION_SLA_HOURS = "manual_review=8"
    assert check_sla_hours(None) == []


def test_queue_and_dashboard_answer_with_broken_sla_hours(world, settings, clock):
    settings.APPLICATION_SLA_HOURS = "offer=4,manual_review=-3"
    make_application(world["company"], S.MANUAL_REVIEW, status_changed_at=entered(25))

    assert _queue(world, "?overdue=true").json()["count"] == 1
    assert _dashboard(world).json()["overdue_count"] == 0  # not submitted in the period


def test_every_default_status_is_a_real_status():
    assert set(DEFAULT_SLA_HOURS) <= set(S.values)


# ───────────────────────── queue ─────────────────────────


def _queue(world, query: str = ""):
    return world["as_bank"].get(f"/api/bank/applications{query}")


def test_queue_item_carries_the_sla(world, clock):
    late = make_application(world["company"], S.MANUAL_REVIEW, status_changed_at=entered(26))
    fresh = make_application(world["company"], S.MANUAL_REVIEW, status_changed_at=entered(23))
    waiting = make_application(world["company"], S.OFFER, status_changed_at=entered(100))

    response = _queue(world)

    assert response.status_code == 200
    assert_matches_contract(response, method="get", path="/api/bank/applications")
    rows = {row["id"]: row for row in response.json()["results"]}
    assert (rows[late.pk]["is_overdue"], rows[late.pk]["overdue_hours"]) == (True, 2)
    assert rows[late.pk]["sla_due_at"] == "2026-10-22T13:00:00+03:00"  # 10:00 UTC
    assert (rows[fresh.pk]["is_overdue"], rows[fresh.pk]["overdue_hours"]) == (False, 0)
    assert rows[waiting.pk]["sla_due_at"] is None and not rows[waiting.pk]["is_overdue"]


def test_overdue_filter_keeps_only_overdue_and_counts_follow(world, clock):
    company = world["company"]
    late = make_application(company, S.MANUAL_REVIEW, status_changed_at=entered(24, SECOND))
    make_application(company, S.MANUAL_REVIEW, status_changed_at=entered(24))  # due right now
    stuck = make_application(company, S.PROCESSING, status_changed_at=entered(1, SECOND))
    make_application(company, S.SIGNING, status_changed_at=entered(500))  # the client's turn
    make_application(company, S.ISSUED, status_changed_at=entered(500))  # final

    body = _queue(world, "?overdue=true").json()

    assert sorted(row["id"] for row in body["results"]) == sorted([late.pk, stuck.pk])
    assert body["count"] == 2
    assert body["counters"]["manual_review"] == 1 and body["counters"]["signing"] == 0
    assert _queue(world, "?overdue=false").json()["count"] == 5


def test_clients_cannot_use_the_overdue_filter(world):
    response = world["as_signatory"].get("/api/bank/applications?overdue=true")

    assert response.status_code == 403


# ───────────────────────── dashboard ─────────────────────────


def _dashboard(world):
    return world["as_bank"].get("/api/bank/dashboard?days=30")


def test_dashboard_overdue_share(world, clock):
    for hours in (30, 25, 2):  # two of three manual reviews are past 24 h
        make_application(
            world["company"],
            S.MANUAL_REVIEW,
            submitted_at=entered(hours + 1),
            status_changed_at=entered(hours),
        )
    make_application(
        world["company"], S.OFFER, submitted_at=entered(200), status_changed_at=entered(199)
    )

    response = _dashboard(world)

    assert_matches_contract(response, method="get", path="/api/bank/dashboard")
    body = response.json()
    assert body["sla_hours"] == {"submitted": 1, "processing": 1, "manual_review": 24, "signed": 1}
    assert (body["sla_open_count"], body["overdue_count"]) == (3, 2)
    assert body["overdue_share"] == "0.6667"


def test_dashboard_share_is_null_without_applications_waiting_for_the_bank(world, clock):
    make_application(
        world["company"], S.OFFER, submitted_at=entered(10), status_changed_at=entered(9)
    )

    body = _dashboard(world).json()

    assert (body["sla_open_count"], body["overdue_count"], body["overdue_share"]) == (0, 0, None)


# ───────────────────────── red team of XP4 ─────────────────────────


def test_approving_an_overdue_review_takes_it_out_of_the_overdue_filter(world, clock):
    late = make_application(
        world["company"],
        S.MANUAL_REVIEW,
        product=world["loan"],
        submitted_at=entered(30),
        status_changed_at=entered(25),
    )
    assert _queue(world, "?overdue=true").json()["count"] == 1

    response = world["as_bank"].post(
        f"/api/bank/applications/{late.pk}/approve", {"version": late.version}, format="json"
    )

    assert response.status_code == 200 and response.json()["application"]["status"] == "offer"
    body = _queue(world, "?overdue=true").json()
    assert body["count"] == 0 and body["counters"]["manual_review"] == 0
    dashboard = _dashboard(world).json()
    assert (dashboard["overdue_count"], dashboard["sla_open_count"]) == (0, 0)


def test_queue_and_dashboard_agree_at_one_moment(world, clock):
    for hours in (2, 23, 25, 50):
        make_application(
            world["company"],
            S.MANUAL_REVIEW,
            submitted_at=entered(hours + 1),
            status_changed_at=entered(hours),
        )
    make_application(
        world["company"], S.PROCESSING, submitted_at=entered(3), status_changed_at=entered(2)
    )

    queue = _queue(world, "?overdue=true").json()
    everything = _queue(world).json()["results"]
    dashboard = _dashboard(world).json()

    flagged = sum(row["is_overdue"] for row in everything)
    assert queue["count"] == sum(queue["counters"].values()) == flagged == 3
    assert dashboard["overdue_count"] == 3 and dashboard["sla_open_count"] == 5


def test_the_same_instant_in_another_time_zone_gives_the_same_answer():
    """Aware datetimes compare by instant: Moscow time and UTC agree on the boundary."""
    moscow = timezone.get_fixed_timezone(180)
    entered_at = entered(24, SECOND)

    in_utc = sla_state(S.MANUAL_REVIEW, entered_at, NOW)
    in_moscow = sla_state(S.MANUAL_REVIEW, entered_at.astimezone(moscow), NOW.astimezone(moscow))

    assert in_utc == in_moscow and in_utc.is_overdue
