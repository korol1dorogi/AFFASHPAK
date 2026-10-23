"""SRC5: new simulator keys — consistent with the company, risk marks only in the two new edges."""

from decimal import Decimal

import pytest

from apps.demo_data import reference as ref
from apps.demo_data.simulators import EGRUL_FLAGS, fns_profile, msp_category

PROFILE = {"employees", "tax_regime", "msp_category", "taxes_paid", "accounts_suspended"}
NEW_EDGES = {"e_accounts_suspended", "e_unreliable_address"}


@pytest.fixture(scope="module")
def edges(dataset) -> dict[str, dict]:
    return {edge["code"]: edge for edge in dataset["edge_cases"]}


def test_population_gets_a_consistent_fns_profile(dataset):
    sims = dataset["simulators"]["transparent_business"]
    checked = 0
    for company in dataset["companies"]:
        data = sims[company["inn"]]["data"]
        if company["_persona"] is not None:
            assert PROFILE.isdisjoint(data)  # data-spec §9.3 pins the personas' answers
            continue
        form = company["legal_form"]
        assert set(data) >= PROFILE
        assert data["accounts_suspended"] is False  # a share would move the D9 stop share
        assert data["tax_regime"] in {name for name, _ in ref.TAX_REGIMES[form]}
        assert (1 if form == "ooo" else 0) <= data["employees"] <= ref.MAX_EMPLOYEES
        if data["tax_regime"] == "psn":
            assert form == "ip" and data["employees"] <= ref.PSN_MAX_EMPLOYEES
        assert data["msp_category"] in {"micro", "small", "medium", "not_msp"}
        assert Decimal(data["taxes_paid"]) > 0
        checked += 1
    assert checked == dataset["meta"]["n_companies"]


def test_egrul_has_kpp_for_ooo_and_no_risk_marks_outside_the_edges(dataset):
    forms = {c["inn"]: c["legal_form"] for c in dataset["companies"]}
    for inn, answer in dataset["simulators"]["egrul"].items():
        data = answer["data"]
        expected_kpp = inn[:4] + ref.KPP_SUFFIX if forms[inn] == "ooo" else None
        assert data["kpp"] == expected_kpp
        assert data["kpp"] is None or (len(data["kpp"]) == 9 and data["kpp"].isdigit())
        assert not any(data[flag] for flag in EGRUL_FLAGS)


def test_accounts_suspended_edge(edges):
    tb = edges["e_accounts_suspended"]["checks"]["transparent_business"]
    assert tb["status"] == "warning"
    assert tb["data"]["accounts_suspended"] is True
    assert set(tb["data"]) >= PROFILE
    assert edges["e_accounts_suspended"]["expected"]["outcome"] == "declined"


def test_unreliable_address_edge(edges, dataset):
    edge = edges["e_unreliable_address"]
    egrul = edge["checks"]["egrul"]
    assert egrul["status"] == "warning"
    assert egrul["data"]["unreliable_address"] is True
    assert not egrul["data"]["unreliable_director"] and not egrul["data"]["pending_exclusion"]
    assert edge["expected"]["outcome"] == "manual_review"
    # The persona's people: no new founder INN, the population's numbering does not shift.
    persona_key = dataset["personas"]["retail_supplier"]["company"]
    persona_inn = next(c["inn"] for c in dataset["companies"] if c["_key"] == persona_key)
    persona_founders = dataset["simulators"]["egrul"][persona_inn]["data"]["founders"]
    assert egrul["data"]["founders"] == persona_founders


def test_older_edges_have_no_risk_marks(edges):
    for code, edge in edges.items():
        if code in NEW_EDGES:
            continue
        assert not edge["checks"]["transparent_business"]["data"].get("accounts_suspended")
        egrul = edge["checks"]["egrul"]
        assert egrul is None or not any(egrul["data"].get(f) for f in EGRUL_FLAGS)


@pytest.mark.parametrize(
    ("employees", "revenue", "category"),
    [
        (15, 120_000_000, "micro"),
        (16, 1_000_000, "small"),
        (10, 120_000_001, "small"),
        (100, 800_000_000, "small"),
        (101, 1_000_000, "medium"),
        (250, 2_000_000_000, "medium"),
        (251, 1_000_000, "not_msp"),
        (10, 2_000_000_001, "not_msp"),
    ],
)
def test_msp_category_follows_209_fz_limits(employees, revenue, category):
    assert msp_category(employees, Decimal(revenue)) == category


class _Picks:
    """A stand-in stream: the lowest value of every range and the regime asked for."""

    def __init__(self, regime: str) -> None:
        self.regime = regime

    def between(self, low: int, high: int) -> int:
        return low

    def weighted(self, items, weights):
        return self.regime

    def decimal_between(self, low: str, high: str, step: str = "0.01") -> Decimal:
        return Decimal(low)


def test_regime_caps():
    big_ip = fns_profile(_Picks("psn"), "ip", Decimal(6_000_000))  # 72 mln a year > ПСН cap
    assert big_ip["tax_regime"] == "usn_income"
    huge_ooo = fns_profile(_Picks("usn_income"), "ooo", Decimal(50_000_000))  # 600 mln > УСН cap
    assert huge_ooo["tax_regime"] == "osn"
    assert huge_ooo["employees"] == 200  # 50 mln a month / 250 000 ₽ per person
    assert huge_ooo["msp_category"] == "medium"
    giant = fns_profile(_Picks("osn"), "ooo", Decimal(100_000_000))
    assert giant["employees"] == ref.MAX_EMPLOYEES  # 400 people capped at 250
    assert giant["msp_category"] == "medium"
    small = fns_profile(_Picks("usn_income"), "ooo", Decimal(100_000))
    assert small["employees"] == 1  # an ООО keeps its director on the payroll
    assert small["taxes_paid"] == "36000.00"  # 1.2 mln a year × 3 %
