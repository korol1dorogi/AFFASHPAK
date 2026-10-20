"""Whole-file checks of docs/data-spec.md §11: structure, ids, types, «демо», cleanliness."""

import re
from datetime import date
from decimal import Decimal

from apps.credit_math.statement import ALLOWED
from apps.demo_data.ids import DEMO_REGION_CODE, is_valid_inn, is_valid_ogrn
from apps.demo_data.reference import GENERATOR_VERSION, SPEC_REF

SECTIONS = {
    "meta", "companies", "users", "memberships", "financial_snapshots", "statements",
    "simulators", "applications", "personas", "edge_cases", "_latent",
}  # fmt: skip
MONEY = re.compile(r"^-?\d+\.\d{2}$")
RATIO = re.compile(r"^-?\d+\.\d{4}$")
MONEY_FIELDS = {
    "cleaned_credit_turnover", "cfads", "debt_service", "revenue", "cogs", "ebitda", "debt",
    "cash", "receivables", "inventory", "payables", "amount", "tax_arrears", "monthly_payment",
    "balance",
}  # fmt: skip
RATIO_FIELDS = {"counterparty_concentration", "revenue_trend", "share"}
DEMO_TEXT_FIELDS = {"name", "full_name", "director_name", "address", "counterparty", "purpose"}


def walk(node, path=()):
    if isinstance(node, dict):
        for key, value in node.items():
            yield from walk(value, (*path, key))
    elif isinstance(node, list):
        for value in node:
            yield from walk(value, path)
    else:
        yield path, node


def test_sections_and_meta(dataset):
    assert set(dataset) == SECTIONS
    meta = dataset["meta"]
    assert meta["generator_version"] == GENERATOR_VERSION == "datagen-2026.10-v1"
    assert meta["spec_ref"] == SPEC_REF
    assert (meta["seed"], meta["as_of"], meta["n_companies"]) == (2026, "2026-10-01", 240)
    assert meta["is_demo"] is True
    for name in ("companies", "users", "memberships", "financial_snapshots", "statements"):
        assert meta["counts"][name] == len(dataset[name])
    assert meta["counts"]["transactions"] == sum(
        len(s["transactions"]) for s in dataset["statements"]
    )
    for name in ("egrul", "transparent_business", "bki"):
        assert meta["counts"][f"simulators.{name}"] == len(dataset["simulators"][name])


def test_ids_valid_unique_and_in_demo_region(dataset):
    """§11.4: companies, counterparties and founders; one INN — one organisation or person."""
    owners: dict[str, str] = {}

    def claim(inn: str, owner: str) -> None:
        assert is_valid_inn(inn), inn
        assert inn[:2] == DEMO_REGION_CODE, inn
        assert owners.setdefault(inn, owner) == owner, (inn, owner, owners[inn])

    for company in dataset["companies"]:
        claim(company["inn"], company["_key"])
        ogrn = company["ogrn"]
        assert is_valid_ogrn(ogrn) and ogrn[3:5] == DEMO_REGION_CODE
        assert ogrn[1:3] == company["registered_at"][2:4]
        expected = (12, 15, "3") if company["legal_form"] == "ip" else (10, 13, "1")
        assert (len(company["inn"]), len(ogrn), ogrn[0]) == expected
    for statement in dataset["statements"]:
        for tx in statement["transactions"]:
            if tx["counterparty_inn"] is not None:
                assert tx["counterparty_inn"][2:4] == "02"
                claim(tx["counterparty_inn"], "cp:" + tx["counterparty"])
    for record in dataset["simulators"]["egrul"].values():
        for founder in record["data"]["founders"]:
            if founder["inn"] not in owners or not founder["inn"].startswith("0001"):
                assert founder["inn"][2:4] == "03"
                claim(founder["inn"], "person:" + founder["name"])


def test_types(dataset):
    """§11.10: money and ratios are strings with fixed decimals, never float."""
    for path, value in walk(dataset):
        assert not isinstance(value, float), path
        field = path[-1] if path else None
        if value is None or isinstance(value, bool):
            continue
        if field in MONEY_FIELDS:
            assert MONEY.fullmatch(value), (path, value)
        elif field in RATIO_FIELDS:
            assert RATIO.fullmatch(value), (path, value)
        elif field in {"date", "registered_at", "period_from", "period_to", "opened_at"}:
            date.fromisoformat(value)
        elif field == "created_at":
            assert re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", value), value


def test_demo_marks(dataset):
    """§11.9: is_demo everywhere, «(демо)» at the end of every text field of §1."""
    assert all(c["is_demo"] is True for c in dataset["companies"])
    assert all(u["profile"]["is_demo"] is True for u in dataset["users"])
    for path, value in walk(dataset):
        if path and path[-1] in DEMO_TEXT_FIELDS and isinstance(value, str):
            assert value.endswith(" (демо)"), (path, value)


def test_statements(dataset):
    """§11.15: positive amounts, allowed categories, dates inside the period, retail without INN."""
    keys = {c["_key"] for c in dataset["companies"]}
    assert len(dataset["statements"]) == len(keys)
    for statement in dataset["statements"]:
        assert statement["company"] in keys
        start = date.fromisoformat(statement["period_from"])
        end = date.fromisoformat(statement["period_to"])
        assert statement["account_masked"][-4:].isdigit() and len(statement["account_masked"]) == 20
        previous = start
        for tx in statement["transactions"]:
            day = date.fromisoformat(tx["date"])
            assert start <= day <= end and day >= previous
            previous = day
            assert tx["direction"] in ALLOWED[tx["category"]]
            assert Decimal(tx["amount"]) > 0
            if tx["counterparty"] in {"Эквайринг (демо)", "Сотрудники (демо)", "ФНС (демо)"}:
                assert tx["counterparty_inn"] is None


def test_snapshot_per_company(dataset):
    keys = [c["_key"] for c in dataset["companies"]]
    assert [s["company"] for s in dataset["financial_snapshots"]] == keys
    assert {s["period"] for s in dataset["financial_snapshots"]} == {"2026-09"}


def test_users_and_memberships_reference_existing_records(dataset):
    users = {u["_key"] for u in dataset["users"]}
    companies = {c["_key"]: c for c in dataset["companies"]}
    assert len(users) == len(dataset["users"])
    assert len({u["username"] for u in dataset["users"]}) == len(users)
    signatories = {}
    for m in dataset["memberships"]:
        assert m["user"] in users and m["company"] in companies
        if m["role"] == "signatory":
            assert m["company"] not in signatories
            signatories[m["company"]] = m["user"]
    names = {u["_key"]: u["profile"]["full_name"] for u in dataset["users"]}
    for key, company in companies.items():
        assert company["director_name"] == names[signatories[key]]


def test_cleanliness(dataset_bytes):
    """§11.16: nothing that looks like a password, token, key, e-mail or phone number."""
    text = dataset_bytes.decode("utf-8")
    assert not re.search(r"[\w.+-]+@[\w-]+\.\w+", text)
    assert not re.search(r"\+7\d{10}|\b8\d{10}\b|\(\d{3}\)\s?\d{3}-\d{2}-\d{2}", text)
    assert not re.search(r"(?i)password|passwd|secret|token|api[_-]?key|пароль", text)
