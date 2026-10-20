"""Auth API: register, login, logout, me, csrf — contract, CSRF, throttling, Me per role."""

import pytest
from rest_framework.test import APIClient
from rest_framework.throttling import SimpleRateThrottle

from apps.core.factories import make_bank_user, make_company, make_user
from apps.core.testing import assert_matches_contract

pytestmark = pytest.mark.django_db

PASSWORD = "demo-password-123"  # make_user's password


def post(client, path, body):
    return client.post(path, body, format="json")


def test_csrf_sets_cookie_and_matches_contract():
    client = APIClient()
    response = client.get("/api/auth/csrf")
    assert response.status_code == 200
    assert_matches_contract(response, method="get", path="/api/auth/csrf")
    assert response.cookies["csrftoken"].value
    assert response.json()["csrf_token"]


def test_register_signs_in_as_client_without_company():
    client = APIClient()
    body = {"username": "new_owner", "password": "Kofe-2026-demo", "full_name": "Ирина Демо"}
    response = post(client, "/api/auth/register", body)
    assert response.status_code == 201, response.json()
    assert_matches_contract(response, method="post", path="/api/auth/register", request_body=body)
    me = response.json()
    assert me["username"] == "new_owner"
    assert me["full_name"] == "Ирина Демо"
    assert me["kind"] == "client"
    assert me["company_id"] is None and me["company_role"] is None
    assert me["is_demo"] is False
    assert client.get("/api/auth/me").json()["id"] == me["id"]


@pytest.mark.parametrize(
    ("body", "field"),
    [
        ({"username": "ab", "password": "Kofe-2026-demo", "full_name": "Демо"}, "username"),
        ({"username": "bad name", "password": "Kofe-2026-demo", "full_name": "Демо"}, "username"),
        ({"username": "owner", "password": "short", "full_name": "Демо"}, "password"),
        ({"username": "owner", "password": "12345678", "full_name": "Демо"}, "password"),
        ({"username": "owner", "password": "Kofe-2026-demo"}, "full_name"),
    ],
)
def test_register_rejects_invalid_input_with_field_errors(body, field):
    response = post(APIClient(), "/api/auth/register", body)
    assert response.status_code == 400
    assert_matches_contract(response, method="post", path="/api/auth/register")
    assert field in response.json()["error"]["details"]


def test_register_rejects_a_taken_username_case_insensitively():
    make_user("Taken")
    body = {"username": "taken", "password": "Kofe-2026-demo", "full_name": "Демо"}
    response = post(APIClient(), "/api/auth/register", body)
    assert response.status_code == 400
    assert response.json()["error"]["details"]["username"] == ["Этот логин уже занят."]


def test_login_returns_me_with_company_and_role():
    user = make_user("director", full_name="Анна Демо")
    company = make_company(members={user: "signatory"})
    client = APIClient()
    body = {"username": "director", "password": PASSWORD}
    response = post(client, "/api/auth/login", body)
    assert response.status_code == 200
    assert_matches_contract(response, method="post", path="/api/auth/login", request_body=body)
    me = response.json()
    assert (me["company_id"], me["company_role"], me["kind"]) == (company.pk, "signatory", "client")
    assert me["is_demo"] is True


def test_login_of_a_bank_user_has_no_company():
    make_bank_user("manager")
    response = post(APIClient(), "/api/auth/login", {"username": "manager", "password": PASSWORD})
    me = response.json()
    assert (me["kind"], me["company_id"], me["company_role"]) == ("bank", None, None)


@pytest.mark.parametrize(
    "body",
    [
        {"username": "director", "password": "wrong-password"},
        {"username": "nobody", "password": PASSWORD},
    ],
)
def test_wrong_credentials_answer_401_without_saying_which(body):
    make_user("director")
    response = post(APIClient(), "/api/auth/login", body)
    assert response.status_code == 401
    assert_matches_contract(response, method="post", path="/api/auth/login")
    assert response.json()["error"] == {
        "code": "invalid_credentials",
        "message": "Неверный логин или пароль.",
    }


def test_inactive_user_cannot_sign_in():
    user = make_user("gone")
    user.is_active = False
    user.save()
    response = post(APIClient(), "/api/auth/login", {"username": "gone", "password": PASSWORD})
    assert response.status_code == 401


def test_login_without_fields_is_400():
    response = post(APIClient(), "/api/auth/login", {})
    assert response.status_code == 400
    assert_matches_contract(response, method="post", path="/api/auth/login")


@pytest.mark.parametrize(
    ("path", "body"),
    [
        ("/api/auth/login", {"username": "director", "password": PASSWORD}),
        (
            "/api/auth/register",
            {"username": "owner", "password": "Kofe-2026-demo", "full_name": "Д"},
        ),
    ],
)
def test_anonymous_login_and_register_require_csrf(path, body):
    make_user("director")
    client = APIClient(enforce_csrf_checks=True)
    response = post(client, path, body)
    assert response.status_code == 403
    assert_matches_contract(response, method="post", path=path)

    token = client.get("/api/auth/csrf").json()["csrf_token"]
    response = client.post(path, body, format="json", HTTP_X_CSRFTOKEN=token)
    assert response.status_code in (200, 201)


def test_logout_requires_csrf_for_a_session_and_ends_it():
    make_user("director")
    client = APIClient(enforce_csrf_checks=True)
    token = client.get("/api/auth/csrf").json()["csrf_token"]
    client.post(
        "/api/auth/login",
        {"username": "director", "password": PASSWORD},
        format="json",
        HTTP_X_CSRFTOKEN=token,
    )
    assert client.post("/api/auth/logout").status_code == 403
    token = client.cookies["csrftoken"].value  # rotated on login
    response = client.post("/api/auth/logout", HTTP_X_CSRFTOKEN=token)
    assert response.status_code == 204
    assert client.get("/api/auth/me").status_code == 401


def test_me_without_session_is_401():
    response = APIClient().get("/api/auth/me")
    assert response.status_code == 401
    assert_matches_contract(response, method="get", path="/api/auth/me")


def test_login_is_throttled(monkeypatch):
    # DRF reads the rates once at import, so patch the class attribute, not settings.
    rates = {**SimpleRateThrottle.THROTTLE_RATES, "login": "3/min"}
    monkeypatch.setattr(SimpleRateThrottle, "THROTTLE_RATES", rates)
    client = APIClient()
    body = {"username": "nobody", "password": "wrong"}
    statuses = [post(client, "/api/auth/login", body).status_code for _ in range(4)]
    assert statuses == [401, 401, 401, 429]
    response = post(client, "/api/auth/login", body)
    assert_matches_contract(response, method="post", path="/api/auth/login")
    assert response.json()["error"]["code"] == "throttled"
