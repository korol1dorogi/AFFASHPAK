"""Company API: registry lookup, create by INN, edit, members — contract, roles, scoping."""

import pytest
from rest_framework.test import APIClient

from apps.accounts.demo import persona_dataset
from apps.business import registry
from apps.business.inn import inn_is_valid
from apps.business.models import Company, Membership
from apps.core.factories import make_bank_user, make_company, make_user
from apps.core.testing import assert_matches_contract

pytestmark = pytest.mark.django_db


def as_user(user) -> APIClient:
    client = APIClient()
    client.force_login(user)
    return client


@pytest.fixture
def registry_inn() -> str:
    """A company the synthetic registry knows (persona 1), not yet in the database."""
    data = persona_dataset()
    key = data["personas"]["coffee_shop"]["company"]
    return next(company["inn"] for company in data["companies"] if company["_key"] == key)


@pytest.fixture
def team(db):
    director = make_user("director", full_name="Анна Демо")
    accountant = make_user("accountant", full_name="Ольга Демо")
    outsider = make_user("outsider")
    company = make_company(members={director: "signatory", accountant: "preparer"})
    other = make_company(members={outsider: "signatory"}, name="ООО Чужая (демо)")
    return {
        "company": company,
        "other": other,
        "director": director,
        "accountant": accountant,
        "outsider": outsider,
        "as_director": as_user(director),
        "as_accountant": as_user(accountant),
        "as_outsider": as_user(outsider),
    }


# ───────────────────────── registry ─────────────────────────


def test_lookup_returns_the_registry_record(registry_inn):
    client = as_user(make_user("owner"))
    path = f"/api/company/lookup?inn={registry_inn}"
    response = client.get(path)
    assert response.status_code == 200
    assert_matches_contract(response, method="get", path="/api/company/lookup")
    record = response.json()
    assert record["inn"] == registry_inn
    assert record["legal_form"] == "ip"
    assert "демо" in record["name"]


def valid_inn_outside_the_registry() -> str:
    """Correct check digits, but no such company in the synthetic registry."""
    prefix = "999999999"
    for last in "0123456789":
        if inn_is_valid(prefix + last) and registry.lookup(prefix + last) is None:
            return prefix + last
    raise AssertionError("no free INN")


@pytest.mark.parametrize(
    ("inn", "status"),
    [("123", 400), ("0012345678", 400), ("000100000171", 400), (None, 404)],
)
def test_lookup_rejects_bad_or_unknown_inn(inn, status):
    """Format, then the ФНС check digits (400), then the registry (404)."""
    inn = inn or valid_inn_outside_the_registry()
    response = as_user(make_user("owner")).get(f"/api/company/lookup?inn={inn}")
    assert response.status_code == status
    assert_matches_contract(response, method="get", path="/api/company/lookup")


def test_lookup_needs_a_session(registry_inn):
    assert APIClient().get(f"/api/company/lookup?inn={registry_inn}").status_code == 401


def test_registry_answers_are_deterministic(registry_inn):
    assert registry.lookup(registry_inn) == registry.lookup(registry_inn)
    assert registry.lookup("0000000000") is None


# ───────────────────────── create, read, edit ─────────────────────────


def test_create_by_inn_fills_registry_fields_and_makes_creator_signatory(registry_inn):
    owner = make_user("owner")
    client = as_user(owner)
    assert client.get("/api/company").status_code == 404
    body = {"inn": registry_inn}
    response = client.post("/api/company", body, format="json")
    assert response.status_code == 201, response.json()
    assert_matches_contract(response, method="post", path="/api/company", request_body=body)
    company = response.json()
    assert company["my_role"] == "signatory"
    assert company["is_demo"] is True
    assert {key: company[key] for key in registry.RECORD_FIELDS} == registry.lookup(registry_inn)
    membership = Membership.objects.get(user=owner)
    assert membership.position == "Индивидуальный предприниматель"

    me = client.get("/api/auth/me").json()
    assert (me["company_id"], me["company_role"]) == (company["id"], "signatory")
    response = client.get("/api/company")
    assert_matches_contract(response, method="get", path="/api/company")
    assert response.json()["id"] == company["id"]


def test_every_registry_inn_has_correct_check_digits():
    assert all(inn_is_valid(inn) for inn in registry._records())


def test_create_rejects_unknown_inn_with_a_field_error():
    response = as_user(make_user("owner")).post(
        "/api/company", {"inn": valid_inn_outside_the_registry()}, format="json"
    )
    assert response.status_code == 400
    assert_matches_contract(response, method="post", path="/api/company")
    assert "inn" in response.json()["error"]["details"]


def test_create_conflicts_when_company_is_taken_or_user_has_one(registry_inn, team):
    make_company(inn=registry_inn, name="Уже подключена (демо)")
    response = as_user(make_user("late")).post("/api/company", {"inn": registry_inn}, format="json")
    assert response.status_code == 409
    assert_matches_contract(response, method="post", path="/api/company")
    assert response.json()["error"]["code"] == "company_taken"

    response = team["as_director"].post("/api/company", {"inn": registry_inn}, format="json")
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "company_exists"


def test_bank_user_cannot_create_or_see_a_company(registry_inn):
    client = as_user(make_bank_user())
    response = client.post("/api/company", {"inn": registry_inn}, format="json")
    assert response.status_code == 403
    assert_matches_contract(response, method="post", path="/api/company")
    assert client.get("/api/company").status_code == 404
    assert not Company.objects.exists()


def test_each_client_sees_only_their_own_company(team):
    assert team["as_director"].get("/api/company").json()["id"] == team["company"].pk
    assert team["as_outsider"].get("/api/company").json()["id"] == team["other"].pk
    assert team["as_accountant"].get("/api/company").json()["my_role"] == "preparer"


def test_signatory_sets_a_short_name_preparer_cannot(team):
    legal = team["company"].name
    body = {"short_name": "Ромашка"}
    response = team["as_director"].patch("/api/company", body, format="json")
    assert response.status_code == 200
    assert_matches_contract(response, method="patch", path="/api/company", request_body=body)
    assert (response.json()["short_name"], response.json()["name"]) == ("Ромашка", legal)

    response = team["as_accountant"].patch("/api/company", {"short_name": "Моя"}, format="json")
    assert response.status_code == 403
    assert_matches_contract(response, method="patch", path="/api/company")
    response = team["as_director"].patch("/api/company", {"short_name": "  "}, format="json")
    assert response.status_code == 200 and response.json()["short_name"] is None  # cleared


def test_registry_fields_are_not_editable(team):
    legal = team["company"].name
    only_name = team["as_director"].patch("/api/company", {"name": "Ромашка"}, format="json")
    assert only_name.status_code == 400
    response = team["as_director"].patch(
        "/api/company", {"short_name": "Ромашка", "name": "X", "inn": "0000000001"}, format="json"
    )
    assert response.status_code == 200
    team["company"].refresh_from_db()
    assert team["company"].inn != "0000000001"
    assert team["company"].name == legal  # the short name never overwrites the legal one


def test_patch_without_company_is_404():
    response = as_user(make_user("owner")).patch("/api/company", {"short_name": "X"}, format="json")
    assert response.status_code == 404
    assert_matches_contract(response, method="patch", path="/api/company")


# ───────────────────────── members ─────────────────────────


def test_members_list_matches_contract(team):
    response = team["as_accountant"].get("/api/company/members")
    assert response.status_code == 200
    assert_matches_contract(response, method="get", path="/api/company/members")
    assert [(m["user"]["full_name"], m["role"]) for m in response.json()] == [
        ("Анна Демо", "signatory"),
        ("Ольга Демо", "preparer"),
    ]


def test_members_without_company_is_404():
    response = as_user(make_user("owner")).get("/api/company/members")
    assert response.status_code == 404
    assert_matches_contract(response, method="get", path="/api/company/members")


def test_preparer_cannot_remove_members(team):
    member = Membership.objects.get(user=team["director"])
    response = team["as_accountant"].delete(f"/api/company/members/{member.pk}")
    assert response.status_code == 403
    assert_matches_contract(response, method="delete", path=f"/api/company/members/{member.pk}")


def test_signatory_removes_a_member_but_not_themselves(team):
    accountant = Membership.objects.get(user=team["accountant"])
    response = team["as_director"].delete(f"/api/company/members/{accountant.pk}")
    assert response.status_code == 204
    assert team["as_accountant"].get("/api/company").status_code == 404

    own = Membership.objects.get(user=team["director"])
    response = team["as_director"].delete(f"/api/company/members/{own.pk}")
    assert response.status_code == 409
    assert_matches_contract(response, method="delete", path=f"/api/company/members/{own.pk}")


def test_foreign_member_id_is_404(team):
    foreign = Membership.objects.get(user=team["outsider"])
    for client in (team["as_director"], team["as_accountant"]):
        response = client.delete(f"/api/company/members/{foreign.pk}")
        assert response.status_code == 404
        assert_matches_contract(
            response, method="delete", path=f"/api/company/members/{foreign.pk}"
        )
    assert Membership.objects.filter(pk=foreign.pk).exists()


# ───────────────────────── invitations ─────────────────────────
# Nobody joins a company without accepting; inviting tells nothing about the login.


def invite(team, username: str, role: str = "preparer"):
    body = {"username": username, "role": role, "position": "Финансовый директор"}
    return team["as_director"].post("/api/company/invitations", body, format="json")


def test_invited_user_joins_only_after_accepting(team):
    newcomer = make_user("newcomer", full_name="Пётр Демо")
    body = {"username": "newcomer", "role": "preparer", "position": "Финансовый директор"}
    response = team["as_director"].post("/api/company/invitations", body, format="json")
    assert response.status_code == 201
    assert_matches_contract(
        response, method="post", path="/api/company/invitations", request_body=body
    )
    assert response.json()["username"] == "newcomer"

    as_newcomer = as_user(newcomer)
    assert as_newcomer.get("/api/company").status_code == 404  # not a member yet
    response = as_newcomer.get("/api/invitations")
    assert response.status_code == 200
    assert_matches_contract(response, method="get", path="/api/invitations")
    [incoming] = response.json()
    assert incoming["company"]["name"] == team["company"].name
    assert incoming["invited_by"] == {"id": team["director"].pk, "full_name": "Анна Демо"}
    assert (incoming["role"], incoming["position"]) == ("preparer", "Финансовый директор")

    path = f"/api/invitations/{incoming['id']}/accept"
    response = as_newcomer.post(path)
    assert response.status_code == 200
    assert_matches_contract(response, method="post", path=path)
    assert response.json()["my_role"] == "preparer"
    assert as_newcomer.get("/api/invitations").json() == []
    assert team["as_director"].get("/api/company/invitations").json() == []
    members = team["as_director"].get("/api/company/members").json()
    assert "Пётр Демо" in [member["user"]["full_name"] for member in members]


@pytest.mark.parametrize("username", ["missing", "outsider", "manager"])
def test_inviting_answers_the_same_for_any_login(team, username):
    """Unknown login, a member of another company and a bank user look exactly alike."""
    make_bank_user("manager")
    response = invite(team, username, role="signatory")
    assert response.status_code == 201
    assert_matches_contract(response, method="post", path="/api/company/invitations")
    assert set(response.json()) == {"id", "username", "role", "position", "created_at"}
    assert not Membership.objects.filter(company=team["company"], user__username=username).exists()


def test_member_of_another_company_cannot_be_pulled_in(team):
    invitation_id = invite(team, "outsider", role="signatory").json()["id"]
    path = f"/api/invitations/{invitation_id}/accept"
    response = team["as_outsider"].post(path)
    assert response.status_code == 409
    assert_matches_contract(response, method="post", path=path)
    assert response.json()["error"]["code"] == "member_exists"
    assert team["as_outsider"].get("/api/company").json()["id"] == team["other"].pk


@pytest.mark.parametrize(
    ("username", "status", "code"),
    [
        ("accountant", 409, "member_exists"),
        ("ACCOUNTANT", 409, "member_exists"),
        ("bad login", 400, "invalid"),
    ],
)
def test_inviting_fails_clearly(team, username, status, code):
    response = invite(team, username)
    assert response.status_code == status
    assert_matches_contract(response, method="post", path="/api/company/invitations")
    assert response.json()["error"]["code"] == code


def test_the_same_login_is_invited_once(team):
    assert invite(team, "newcomer").status_code == 201
    response = invite(team, "NewComer")
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "invitation_exists"
    assert len(team["as_accountant"].get("/api/company/invitations").json()) == 1


def test_preparer_sees_but_cannot_invite_or_cancel(team):
    invitation_id = invite(team, "newcomer").json()["id"]
    response = team["as_accountant"].get("/api/company/invitations")
    assert response.status_code == 200
    assert_matches_contract(response, method="get", path="/api/company/invitations")
    body = {"username": "someone", "role": "signatory", "position": "Директор"}
    response = team["as_accountant"].post("/api/company/invitations", body, format="json")
    assert response.status_code == 403
    path = f"/api/company/invitations/{invitation_id}"
    response = team["as_accountant"].delete(path)
    assert response.status_code == 403
    assert_matches_contract(response, method="delete", path=path)


def test_cancelled_invitation_cannot_be_accepted(team):
    newcomer = make_user("newcomer")
    invitation_id = invite(team, "newcomer").json()["id"]
    path = f"/api/company/invitations/{invitation_id}"
    response = team["as_director"].delete(path)
    assert response.status_code == 204
    assert_matches_contract(response, method="delete", path=path)
    assert as_user(newcomer).get("/api/invitations").json() == []
    response = as_user(newcomer).post(f"/api/invitations/{invitation_id}/accept")
    assert response.status_code == 404
    assert not Membership.objects.filter(user=newcomer).exists()


def test_declined_invitation_is_gone(team):
    newcomer = make_user("newcomer")
    invitation_id = invite(team, "newcomer").json()["id"]
    path = f"/api/invitations/{invitation_id}/decline"
    response = as_user(newcomer).post(path)
    assert response.status_code == 204
    assert_matches_contract(response, method="post", path=path)
    assert team["as_director"].get("/api/company/invitations").json() == []
    assert as_user(newcomer).post(f"/api/invitations/{invitation_id}/accept").status_code == 404


def test_foreign_invitation_id_is_404(team):
    """Someone else's invitation: neither another user nor another company can touch it."""
    make_user("newcomer")
    invitation_id = invite(team, "newcomer").json()["id"]
    for action in ("accept", "decline"):
        path = f"/api/invitations/{invitation_id}/{action}"
        response = team["as_accountant"].post(path)
        assert response.status_code == 404
        assert_matches_contract(response, method="post", path=path)
    path = f"/api/company/invitations/{invitation_id}"
    response = team["as_outsider"].delete(path)
    assert response.status_code == 404
    assert_matches_contract(response, method="delete", path=path)
    assert team["as_director"].get("/api/company/invitations").json() != []


def test_bank_user_has_no_invitations(team):
    invitation_id = invite(team, "manager").json()["id"]
    as_bank = as_user(make_bank_user("manager"))
    response = as_bank.get("/api/invitations")
    assert response.status_code == 403
    assert_matches_contract(response, method="get", path="/api/invitations")
    assert as_bank.post(f"/api/invitations/{invitation_id}/accept").status_code == 403


# ───────────────────────── integrations ─────────────────────────


def test_company_says_what_is_connected(team):
    body = team["as_director"].get("/api/company").json()
    assert body["integrations"] == {"bank_account": None, "edo": None}
    assert body["short_name"] is None


@pytest.mark.parametrize("source", ["bank_account", "edo"])
def test_connect_brings_the_statement_and_is_remembered(registry_inn, source):
    owner = make_user("owner")
    client = as_user(owner)
    client.post("/api/company", {"inn": registry_inn}, format="json")
    path = f"/api/company/integrations/{source}/connect"
    response = client.post(path)
    assert response.status_code == 200
    assert_matches_contract(response, method="post", path=path)
    body = response.json()
    assert (body["source"], body["status"], body["is_demo"]) == (source, "connected", True)
    assert body["snapshot"]["cfads"] == "450000.00"  # persona 1, data-spec.md §9.2
    integrations = client.get("/api/company").json()["integrations"]
    assert integrations[source] is not None
    assert client.post(path).status_code == 200  # again: no duplicate rows
    assert client.get("/api/company/metrics").json()["snapshot"] is not None


def test_connect_rules(team, settings, registry_inn):
    assert team["as_director"].post("/api/company/integrations/sms/connect").status_code == 404
    assert (
        as_user(make_user("lonely")).post("/api/company/integrations/edo/connect").status_code
        == 404
    )
    bank = as_user(make_bank_user())
    response = bank.post("/api/company/integrations/edo/connect")
    assert response.status_code == 403
    assert APIClient().post("/api/company/integrations/edo/connect").status_code == 401


def test_a_switched_off_bank_answers_503(registry_inn):
    from apps.integrations import flags

    owner = make_user("owner")
    client = as_user(owner)
    client.post("/api/company", {"inn": registry_inn}, format="json")
    flags.set_failing("bank_account", True)
    try:
        path = "/api/company/integrations/bank_account/connect"
        response = client.post(path)
        assert response.status_code == 503
        assert_matches_contract(response, method="post", path=path)
    finally:
        flags.reset()
