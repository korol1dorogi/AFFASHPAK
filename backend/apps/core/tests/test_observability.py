"""OPS5: correlation id, JSON logs, the request_id through Celery, the application's history."""

import io
import json
import logging
import sys
import uuid
from types import SimpleNamespace

import pytest
from django.http import HttpResponse
from django.test import RequestFactory
from rest_framework.test import APIClient

from apps.accounts.demo import seed
from apps.applications.models import BKI_CONSENT_VERSION, ApplicationEvent, ApplicationStatus
from apps.business.models import Membership
from apps.core import context
from apps.core.factories import make_application, make_company, make_user
from apps.core.logs import ContextFilter, JsonFormatter, TextFormatter
from apps.core.middleware import RequestIdMiddleware
from apps.integrations.flags import reset as reset_failures
from config import celery as celery_signals

S = ApplicationStatus
CLIENT_ID = "client-req-0001"


@pytest.fixture
def logs():
    """Every record as the console handler writes it: JSON lines, with the context filter."""
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.addFilter(ContextFilter())
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    level = root.level
    root.addHandler(handler)
    root.setLevel(logging.INFO)

    def lines() -> list[dict]:
        return [json.loads(line) for line in stream.getvalue().splitlines()]

    lines.raw = stream.getvalue  # type: ignore[attr-defined]
    yield lines
    root.removeHandler(handler)
    root.setLevel(level)


def _access(lines: list[dict]) -> list[dict]:
    return [line for line in lines if line["logger"] == "apps.core.access"]


def _is_uuid4(value: str) -> bool:
    try:
        return uuid.UUID(value).version == 4
    except ValueError:
        return False


# ───────────────────────── X-Request-ID ─────────────────────────


@pytest.mark.django_db
def test_a_valid_request_id_comes_back_and_reaches_the_logs(logs):
    response = APIClient().get("/api/auth/csrf", HTTP_X_REQUEST_ID=CLIENT_ID)
    assert response["X-Request-ID"] == CLIENT_ID
    [line] = _access(logs())
    assert line["request_id"] == CLIENT_ID


@pytest.mark.django_db
@pytest.mark.parametrize(
    "header",
    [
        None,
        "",
        "short",  # under 8
        "a" * 65,
        "abc 12345678",
        "abc12345678\nfake line",
        'abc12345678"}',
        "абвгдежзик",
        "abc_12345678",
    ],
)
def test_a_missing_or_malformed_request_id_is_replaced(logs, header):
    extra = {} if header is None else {"HTTP_X_REQUEST_ID": header}
    response = APIClient().get("/api/auth/csrf", **extra)
    issued = response["X-Request-ID"]
    assert _is_uuid4(issued)
    assert issued != header
    assert _access(logs())[0]["request_id"] == issued
    if header:
        assert header not in logs.raw()


@pytest.mark.django_db
def test_one_access_line_per_request_without_the_query_string(logs):
    user = make_user("director")
    client = APIClient()
    client.force_login(user)
    response = client.get("/api/auth/me?search=7700000000", HTTP_X_REQUEST_ID=CLIENT_ID)
    assert response.status_code == 200

    [line] = _access(logs())
    assert line["method"] == "GET"
    assert line["path"] == "/api/auth/me"
    assert line["status"] == 200
    assert line["user_id"] == user.pk
    assert isinstance(line["duration_ms"], float)
    assert line["level"] == "INFO"
    assert "7700000000" not in logs.raw()


@pytest.mark.django_db
def test_the_access_line_names_the_application_from_the_url(logs):
    director = make_user("director")
    application = make_application(make_company(members={director: "signatory"}))
    client = APIClient()
    client.force_login(director)
    client.get(f"/api/applications/{application.pk}")
    client.get(f"/api/applications/{application.pk}/documents")
    assert [line.get("application_id") for line in _access(logs())] == [application.pk] * 2


def test_a_crashing_view_still_gets_an_access_line_and_a_clean_context(logs):
    def crash(request):
        raise RuntimeError("boom")

    middleware = RequestIdMiddleware(crash)
    with pytest.raises(RuntimeError):
        middleware(RequestFactory().get("/api/whatever", HTTP_X_REQUEST_ID=CLIENT_ID))
    [line] = _access(logs())
    assert line["status"] == 500
    assert line["level"] == "ERROR"
    assert line["request_id"] == CLIENT_ID
    assert context.current() == {"request_id": None, "application_id": None, "user_id": None}


def test_a_newline_in_the_path_cannot_forge_a_line(logs):
    middleware = RequestIdMiddleware(lambda request: HttpResponse(status=404))
    middleware(RequestFactory().get("/api/x%0A{fake}"))
    [line] = _access(logs())
    assert line["path"] == "/api/x?{fake}"


@pytest.mark.django_db
def test_the_context_does_not_leak_between_requests(logs):
    client = APIClient()
    first = client.get("/api/auth/csrf")["X-Request-ID"]
    assert context.current() == {"request_id": None, "application_id": None, "user_id": None}
    second = client.get("/api/auth/csrf")["X-Request-ID"]
    assert first != second
    assert [line["request_id"] for line in _access(logs())] == [first, second]


# ───────────────────────── format ─────────────────────────


def _record(**extra) -> logging.LogRecord:
    try:
        raise ValueError("bad value")
    except ValueError:
        exc_info = sys.exc_info()
    record = logging.LogRecord(
        "apps.test", logging.ERROR, __file__, 1, "failed %s", ("x",), exc_info
    )
    for name, value in extra.items():
        setattr(record, name, value)
    ContextFilter().filter(record)
    return record


def test_the_json_formatter_writes_one_valid_object_with_the_fields():
    tokens = context.bind(request_id=CLIENT_ID, application_id=42, user_id=7)
    try:
        record = _record(
            method="POST", path="/api/x", status=500, duration_ms=1.5, inn="7700000000"
        )
    finally:
        context.reset(tokens)
    output = JsonFormatter().format(record)
    assert "\n" not in output
    entry = json.loads(output)
    assert entry["ts"].endswith("Z")
    assert entry["level"] == "ERROR"
    assert entry["logger"] == "apps.test"
    assert entry["message"] == "failed x"
    assert (entry["request_id"], entry["application_id"], entry["user_id"]) == (CLIENT_ID, 42, 7)
    assert (entry["method"], entry["path"], entry["status"], entry["duration_ms"]) == (
        "POST",
        "/api/x",
        500,
        1.5,
    )
    assert "ValueError: bad value" in entry["exc"]
    assert "inn" not in entry  # only whitelisted extras are written


def test_fields_that_are_not_known_are_left_out():
    entry = json.loads(JsonFormatter().format(_record()))
    assert "request_id" not in entry
    assert "application_id" not in entry


def test_the_text_format_shows_the_correlation_fields():
    tokens = context.bind(request_id=CLIENT_ID, application_id=42)
    try:
        output = TextFormatter().format(_record())
    finally:
        context.reset(tokens)
    assert f"[rid={CLIENT_ID} app=42 user=None] failed x" in output


def test_the_settings_use_the_context_filter_on_the_console():
    from django.conf import settings

    console = settings.LOGGING["handlers"]["console"]
    assert console["filters"] == ["context"]
    assert console["formatter"] in {"json", "text"}
    assert settings.MIDDLEWARE[0] == "apps.core.middleware.RequestIdMiddleware"


# ───────────────────────── Celery ─────────────────────────


def _task(name: str = "pipeline.run", **request):
    return SimpleNamespace(name=name, request=SimpleNamespace(**request))


def test_publish_puts_the_request_id_into_the_task_headers():
    headers: dict = {}
    tokens = context.bind(request_id=CLIENT_ID)
    try:
        celery_signals._publish_request_id(headers=headers)
    finally:
        context.reset(tokens)
    assert headers["request_id"] == CLIENT_ID


def test_a_task_queued_without_a_request_gets_its_own_id():
    headers: dict = {}
    celery_signals._publish_request_id(headers=headers)
    assert headers["request_id"].startswith("task-")
    assert context.is_valid_request_id(headers["request_id"])


@pytest.mark.parametrize(
    ("args", "kwargs"), [((42,), {}), ((), {"application_id": 42})], ids=["args", "kwargs"]
)
def test_prerun_binds_the_request_id_and_the_application_and_postrun_clears_them(args, kwargs):
    task = _task(request_id=CLIENT_ID, headers={"request_id": CLIENT_ID})
    celery_signals._bind_task_context(task_id="t1", task=task, args=args, kwargs=kwargs)
    assert context.request_id.get() == CLIENT_ID
    assert context.application_id.get() == 42
    celery_signals._unbind_task_context(task_id="t1")
    assert context.current() == {"request_id": None, "application_id": None, "user_id": None}


def test_prerun_refuses_a_malformed_header():
    task = _task(request_id="bad id\n", headers=None)
    celery_signals._bind_task_context(task_id="t2", task=task, args=(42,), kwargs={})
    try:
        assert context.request_id.get().startswith("task-")
    finally:
        celery_signals._unbind_task_context(task_id="t2")


def test_eager_keeps_the_request_id_of_the_request_around_it():
    outer = context.bind(request_id=CLIENT_ID, application_id=7)
    try:
        task = _task(name="pipeline.disburse", headers=None)  # apply(): nothing was published
        celery_signals._bind_task_context(task_id="t3", task=task, args=(42,), kwargs={})
        assert context.request_id.get() == CLIENT_ID
        assert context.application_id.get() == 42
        celery_signals._unbind_task_context(task_id="t3")
        assert context.current()["request_id"] == CLIENT_ID
        assert context.current()["application_id"] == 7  # restored, not wiped
    finally:
        context.reset(outer)


@pytest.mark.django_db
def test_a_task_applied_in_process_logs_with_the_request_id(logs, seeded_coffee_shop):
    from apps.pipeline import celery_tasks

    application = seeded_coffee_shop
    tokens = context.bind(request_id=CLIENT_ID)
    try:
        celery_tasks.run_pipeline.apply(args=(application.pk,))
    finally:
        context.reset(tokens)
    worker = [line for line in logs() if line["logger"] == "apps.pipeline.celery_tasks"]
    assert worker
    assert worker[0]["request_id"] == CLIENT_ID
    assert worker[0]["application_id"] == application.pk
    assert context.current()["request_id"] is None


# ───────────────────────── the application's history ─────────────────────────


@pytest.mark.django_db
def test_each_journal_event_is_one_log_line(logs):
    director = make_user("director")
    application = make_application(make_company(members={director: "signatory"}))
    event = ApplicationEvent.objects.create(
        application=application,
        kind="status_changed",
        from_status=S.DRAFT,
        to_status=S.SUBMITTED,
        actor_kind="client",
        actor=director,
        message="Демо: секретный текст сообщения",
        payload={"text_version": "x"},
    )
    event.save()  # an update is not a new event

    [line] = [line for line in logs() if line["logger"] == "apps.core.journal"]
    assert line["application_id"] == application.pk
    assert line["event_id"] == event.pk
    assert (line["kind"], line["from_status"], line["to_status"], line["actor_kind"]) == (
        "status_changed",
        "draft",
        "submitted",
        "client",
    )
    assert "draft → submitted" in line["message"]
    assert "секретный" not in logs.raw()


@pytest.fixture
def seeded_coffee_shop(db):
    """Persona 1 (synthetic): a submitted overdraft application, ready for the pipeline."""
    from apps.pipeline.tests.test_personas import _application

    seed()
    yield _application("demo_coffee_shop", "overdraft_basic", "900000.00", 12)
    reset_failures()


@pytest.mark.django_db(transaction=True)
def test_one_request_id_shows_the_whole_history_without_personal_data(logs, settings):
    """Persona 1 submits through the API; the pipeline runs on commit, in-process (pytest)."""
    seed()
    try:
        settings.DEMO_MODE = True
        client = APIClient()
        client.post("/api/demo/login", {"persona": "coffee_shop"}, format="json")
        purpose = "Демо: зарплата до поступления оплаты"
        body = {
            "need_type": "cash_gap",
            "purpose": purpose,
            "requested_amount": "900000.00",
            "term_months": 12,
            "product_code": "overdraft_basic",
        }
        app_id = client.post("/api/applications", body, format="json").json()["id"]
        response = client.post(
            f"/api/applications/{app_id}/submit",
            {"bki_consent": True, "consent_version": BKI_CONSENT_VERSION},
            format="json",
            HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4()),
            HTTP_X_REQUEST_ID=CLIENT_ID,
        )
        assert response.status_code == 200
        assert response["X-Request-ID"] == CLIENT_ID
    finally:
        reset_failures()

    chain = [line for line in logs() if line.get("request_id") == CLIENT_ID]
    journal = [line for line in chain if line["logger"] == "apps.core.journal"]
    assert {line["application_id"] for line in chain} == {app_id}
    transitions = [
        (line["from_status"], line["to_status"]) for line in journal if line.get("to_status")
    ]
    assert transitions[:2] == [("draft", "submitted"), ("submitted", "processing")]
    assert transitions[-1] == ("processing", "offer")
    kinds = [line["kind"] for line in journal]
    assert "check_completed" in kinds
    assert "score_calculated" in kinds
    assert {line["source"] for line in journal if line["kind"] == "check_completed"} >= {"egrul"}
    assert _access(chain)[-1]["path"] == f"/api/applications/{app_id}/submit"

    membership = Membership.objects.select_related("company", "user__profile").get(
        user__username="demo_coffee_shop"
    )
    raw = logs.raw()
    for secret in (
        membership.company.inn,
        membership.company.name,
        membership.user.profile.full_name,
        "900000",
        purpose,
        client.cookies["sessionid"].value,
        client.cookies["csrftoken"].value,
    ):
        assert secret not in raw
