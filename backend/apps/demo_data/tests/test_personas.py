"""Personas 1–8 to the kopeck: docs/data-spec.md §9 and decision-model.md §8 (D4).

Product parameters (alpha 0.3, beta 0.9, 24 % for 12 months, min DSCR 1.25) are those of the D3
catalog draft; they are not part of the generated data.
"""

from datetime import date
from decimal import Decimal

import pytest

from apps.credit_math import (
    ccc,
    debt_to_ebitda,
    factoring_advance,
    max_loan_by_dscr,
    overdraft_limit,
    working_capital_need,
)
from apps.credit_math.statement import monthly_totals, statement_metrics
from apps.demo_data.ids import company_ids

D = Decimal

# §9.1
REQUISITES = {
    "coffee_shop": ("ip", "000100000170", "323000100000013", "56.10", "food_service", "2023-10-01",
                    "active", "ИП Лаврова Анна Сергеевна — кофейня «Зерно и пар» (демо)"),
    "retail_supplier": ("ooo", "0001000028", "1200001000022", "46.90", "wholesale", "2020-10-01",
                        "active", "ООО «Северный поставщик» (демо)"),
    "garden_store": ("ip", "000100000318", "318000100000031", "47.76", "garden", "2018-10-01",
                     "active",
                     "ИП Соколова Марина Викторовна — садовый центр «Зелёный двор» (демо)"),
    "furniture_maker": ("ooo", "0001000042", "1140001000040", "31.09", "manufacturing",
                        "2014-10-01", "active", "ООО «Дубрава Мебель» (демо)"),
    "dependent_supplier": ("ooo", "0001000050", "1220001000053", "46.90", "wholesale",
                           "2022-10-01", "active", "ООО «Опора Снаб» (демо)"),
    "liquidating_company": ("ooo", "0001000067", "1210001000065", "62.01", "services",
                            "2021-10-01", "liquidating", "ООО «Вектор Сервис» (демо)"),
    "bki_outage": ("ip", "000100000702", "323000100000079", "56.10", "food_service", "2023-10-01",
                   "active", "ИП Миронов Артём Валерьевич — кофейня «Северный ветер» (демо)"),
    "equipment_no_collateral": ("ooo", "0001000081", "1170001000080", "25.62", "manufacturing",
                                "2017-10-01", "active", "ООО «Ковка и Фреза» (демо)"),
}  # fmt: skip

DIRECTORS = {
    "coffee_shop": "Лаврова Анна Сергеевна",
    "retail_supplier": "Громов Илья Петрович",
    "garden_store": "Соколова Марина Викторовна",
    "furniture_maker": "Орлов Сергей Николаевич",
    "dependent_supplier": "Карпов Денис Андреевич",
    "liquidating_company": "Зуев Павел Олегович",
    "bki_outage": "Миронов Артём Валерьевич",
    "equipment_no_collateral": "Тимофеев Роман Ильич",
}

# §9.2: (cleaned_credit_turnover, cfads, debt_service, revenue, cogs, ebitda, debt, cash,
#        receivables, inventory, payables, counterparty_concentration, revenue_trend)
N = None
SNAPSHOTS = {
    "coffee_shop": ("3000000.00", "450000.00", "0.00", N, N, N, N, N, N, N, N, "0.1000", "1.0500"),
    "retail_supplier": ("8000000.00", "550000.00", "250000.00", N, N, "7000000.00",
                        "18600000.00", "600000.00", N, N, N, "0.6000", "1.0000"),
    "garden_store": ("3041666.67", "300000.00", "50000.00", "36500000.00", "29200000.00", N, N,
                     N, "4500000.00", "2400000.00", "1600000.00", "0.0500", "0.9500"),
    "furniture_maker": ("12000000.00", "1800000.00", "1000000.00", N, N, N, N, N, N, N, N,
                        "0.4000", "0.9700"),
    "dependent_supplier": ("2700000.00", "330000.00", "300000.00", N, N, "4000000.00",
                           "16800000.00", "0.00", N, N, N, "0.8000", "0.8000"),
    "liquidating_company": ("1200000.00", "96000.00", "0.00", N, N, N, N, N, N, N, N, "0.2000",
                            "0.9000"),
    "bki_outage": ("3000000.00", "450000.00", "0.00", N, N, N, N, N, N, N, N, "0.1000", "1.0500"),
    "equipment_no_collateral": ("12000000.00", "1800000.00", "1000000.00", N, N, N, N, N, N, N, N,
                                "0.4000", "1.0000"),
}  # fmt: skip
SNAPSHOT_FIELDS = (
    "cleaned_credit_turnover", "cfads", "debt_service", "revenue", "cogs", "ebitda", "debt",
    "cash", "receivables", "inventory", "payables", "counterparty_concentration", "revenue_trend",
)  # fmt: skip

# §9.2 monthly totals, thousands of rubles, months 2025-04 … 2026-09.
REVENUE = {
    "coffee_shop": [2863, 2990, 3060, 3130, 3114, 2980, 2902, 2825, 2926, 2730, 2681, 2902, 3004,
                    3136, "3208.8", 3287, 3269, "3129.2"],
    "retail_supplier": [8000, 8160, 8000, 7680, 7840, 8320, 8480, 8320, 8320, 7360, 7520, 8000,
                        8000, 8160, 8000, 7680, 7840, 8320],
    "garden_store": [5751, 6999, 6019, 4416, 3455, 2502, 1569, 1094, 1089, 929, 1234, 2764, 5505,
                     6700, "5761.65", 4195, 3282, "2377.35"],
    "furniture_maker": [12603, 12324, 12047, 11526, 11741, 12810, 13139, 13105, 13314, 10262,
                        11079, 12252, 12221, 11951, "11682.31", 11180, 11389, "12425.69"],
    "dependent_supplier": [3000] * 6 + [2800] * 9 + [2400] * 3,
    "liquidating_company": [1327, 1316, 1239, 1164, 1218, 1334, 1320, 1308, 1420, 1163, 1153,
                            1203, 1193, 1182, "1113.6", 1048, 1096, "1200.4"],
}  # fmt: skip
OPEX = {
    "coffee_shop": [2434, 2542, 2601, 2661, 2647, 2533, 2467, 2401, 2487, 2321, 2279, 2467, 2553,
                    2666, 2727, 2794, 2779, 2659],
    "retail_supplier": [7450, 7599, 7450, 7152, 7301, 7748, 7897, 7748, 7748, 6854, 7003, 7450,
                        7450, 7599, 7450, 7152, 7301, 7748],
    "garden_store": [5184, 6309, 5425, 3980, 3114, 2255, 1414, 986, 982, 837, 1112, 2491, 4962,
                     6039, 5193, 3781, 2958, 2145],
    "furniture_maker": [10713, 10475, 10240, 9797, 9980, 10889, 11168, 11139, 11317, 8723, 9417,
                        10414, 10388, 10158, 9930, 9503, 9681, 10562],
    "dependent_supplier": [2633] * 6 + [2458] * 9 + [2107, 2107, 2104],
    "liquidating_company": [1221, 1211, 1140, 1071, 1121, 1227, 1214, 1203, 1306, 1070, 1061,
                            1107, 1098, 1087, 1025, 964, 1008, 1105],
}  # fmt: skip
REVENUE["bki_outage"], OPEX["bki_outage"] = REVENUE["coffee_shop"], OPEX["coffee_shop"]
# Persona 8 (§9.2): tau = 1.00, so months 13–18 repeat 1–6; O = 0.85 M without rounding.
_P8_FIRST = [12240, 12000, 11760, 11280, 11520, 12600]
_P8_REVENUE = [*_P8_FIRST, 12960, 12960, 13200, 10200, 11040, 12240, *_P8_FIRST]
REVENUE["equipment_no_collateral"] = _P8_REVENUE
OPEX["equipment_no_collateral"] = [str(D(m) * D("0.85")) for m in _P8_REVENUE]
K_WINDOW = {
    "coffee_shop": 3_600_000, "retail_supplier": 57_600_000, "garden_store": 1_825_000,
    "furniture_maker": 57_600_000, "dependent_supplier": 25_920_000,
    "liquidating_company": 2_880_000, "bki_outage": 3_600_000,
    "equipment_no_collateral": 57_600_000,
}  # fmt: skip
# §9.2 «Плательщики и долги»: (largest payer, other payers' count, retail, obligations)
PAYERS = {
    "coffee_shop": ("ООО «Офис на Северной» (демо)", 0, True, []),
    "retail_supplier": ("ООО «Сеть Домашний» (демо)", 2, False, [("loan", "250000.00")]),
    "garden_store": ("ООО «Ландшафт-Про» (демо)", 1, True, [("loan", "50000.00")]),
    "furniture_maker": ("ООО «Интерьер Групп» (демо)", 3, False,
                        [("loan", "600000.00"), ("leasing", "400000.00")]),
    "dependent_supplier": ("ООО «ТоргМаркет» (демо)", 2, False,
                           [("loan", "200000.00"), ("loan", "100000.00")]),
    "liquidating_company": ("ООО «Кедр Консалт» (демо)", 5, False, []),
    "bki_outage": ("ООО «Офис на Северной» (демо)", 0, True, []),
    "equipment_no_collateral": ("ООО «Гидропривод Сервис» (демо)", 3, False,
                                [("loan", "600000.00"), ("leasing", "400000.00")]),
}  # fmt: skip


def thousands(values) -> list[Decimal]:
    return [D(str(v)) * 1000 for v in values]


@pytest.fixture(scope="module")
def by_key(dataset):
    return {
        "company": {c["_key"]: c for c in dataset["companies"]},
        "snapshot": {s["company"]: s for s in dataset["financial_snapshots"]},
        "statement": {s["company"]: s for s in dataset["statements"]},
        "user": {u["_key"]: u for u in dataset["users"]},
    }


def persona_company(dataset, by_key, code):
    return by_key["company"][dataset["personas"][code]["company"]]


@pytest.mark.parametrize("code", list(REQUISITES))
def test_requisites(dataset, by_key, code):
    company = persona_company(dataset, by_key, code)
    form, inn, ogrn, okved, group, registered, status, name = REQUISITES[code]
    assert (company["legal_form"], company["inn"], company["ogrn"]) == (form, inn, ogrn)
    assert (company["okved"], company["_okved_group"], company["registered_at"]) == (
        okved, group, registered,
    )  # fmt: skip
    assert (company["registry_status"], company["name"]) == (status, name)
    assert company["director_name"] == DIRECTORS[code] + " (демо)"
    assert company["_persona"] == code and company["region"] == "Демо-регион (00)"
    assert company["created_at"] == "2026-10-01T00:00:00Z"
    number = int(inn[4:9] if form == "ooo" else inn[4:10])
    assert company_ids(form, number, int(registered[:4])) == (inn, ogrn)


def test_persona_1_address_from_the_spec(dataset, by_key):
    company = persona_company(dataset, by_key, "coffee_shop")
    assert company["address"] == "000001, Демо-регион, г. Условный, ул. Кофейная, д. 7 (демо)"


@pytest.mark.parametrize("code", list(SNAPSHOTS))
def test_snapshot_strings_equal_the_table(dataset, by_key, code):
    snapshot = by_key["snapshot"][dataset["personas"][code]["company"]]
    assert (snapshot["period"], snapshot["source"]) == ("2026-09", "simulator")
    assert tuple(snapshot[f] for f in SNAPSHOT_FIELDS) == SNAPSHOTS[code]


@pytest.mark.parametrize("code", list(SNAPSHOTS))
def test_snapshot_is_recomputed_from_the_statement(dataset, by_key, code):
    key = dataset["personas"][code]["company"]
    statement, snapshot = by_key["statement"][key], by_key["snapshot"][key]
    metrics = statement_metrics(
        statement["transactions"], date(2026, 10, 1),
        period_from=date.fromisoformat(statement["period_from"]),
    )  # fmt: skip
    assert len(metrics.months) == 18
    assert str(metrics.cleaned_credit_turnover.value) == snapshot["cleaned_credit_turnover"]
    assert str(metrics.cfads.value) == snapshot["cfads"]
    assert str(metrics.debt_service.value) == snapshot["debt_service"]
    assert str(metrics.counterparty_concentration.value) == snapshot["counterparty_concentration"]
    assert str(metrics.revenue_trend.value) == snapshot["revenue_trend"]


@pytest.mark.parametrize("code", list(REVENUE))
def test_monthly_totals_equal_the_tables(dataset, by_key, code):
    key = dataset["personas"][code]["company"]
    statement = by_key["statement"][key]
    totals = monthly_totals(statement["transactions"], [f"{y}-{m:02d}" for y, m in _months()])
    assert [totals[p].inflow for p in totals] == thousands(REVENUE[code])
    assert [totals[p].opex for p in totals] == thousands(OPEX[code])
    top_name, others, retail, obligations = PAYERS[code]
    window = list(totals)[6:]
    top_inn = next(
        tx["counterparty_inn"] for tx in statement["transactions"] if tx["counterparty"] == top_name
    )
    assert sum(totals[p].inflow_by_payer[top_inn] for p in window) == K_WINDOW[code]
    payer_inns = {inn for p in window for inn in totals[p].inflow_by_payer}
    assert len(payer_inns) == 1 + others
    retail_txs = [t for t in statement["transactions"] if t["counterparty"] == "Эквайринг (демо)"]
    assert bool(retail_txs) is retail
    assert all(t["counterparty_inn"] is None for t in retail_txs)
    bki = dataset["simulators"]["bki"][by_key["company"][key]["inn"]]["data"]
    assert [(o["kind"], o["monthly_payment"]) for o in bki["obligations"]] == obligations
    loan_days = {
        t["date"][8:] for t in statement["transactions"] if t["category"] == "loan_payment"
    }
    assert loan_days <= {"15"}
    assert not [t for t in statement["transactions"] if t["category"] == "loan"]


def _months():
    year, month = 2025, 4
    for _ in range(18):
        yield year, month
        year, month = (year + 1, 1) if month == 12 else (year, month + 1)


def snapshot_of(dataset, by_key, code) -> dict[str, Decimal | None]:
    raw = by_key["snapshot"][dataset["personas"][code]["company"]]
    return {f: None if raw[f] is None else D(raw[f]) for f in SNAPSHOT_FIELDS}


def test_d4_reference_numbers(dataset, by_key):
    """decision-model.md §8: the numbers the decision model expects from these snapshots."""
    p1 = snapshot_of(dataset, by_key, "coffee_shop")
    assert overdraft_limit(p1["cleaned_credit_turnover"], D("0.3")) == D("900000.00")
    assert factoring_advance(D("5000000"), D("0.9")) == D("4500000.00")  # persona 2, §9.3

    p3 = snapshot_of(dataset, by_key, "garden_store")
    cycle = ccc(p3["revenue"], p3["cogs"], p3["receivables"], p3["inventory"], p3["payables"])
    assert (cycle.dso.value, cycle.dio.value, cycle.dpo.value, cycle.ccc.value) == (45, 30, 20, 55)
    need = working_capital_need(p3["receivables"], p3["inventory"], p3["payables"])
    assert need == D("5300000.00")
    cap = max_loan_by_dscr(p3["cfads"], p3["debt_service"], D("0.24"), 12)
    assert cap.value == D("2009314.00")

    p2 = snapshot_of(dataset, by_key, "retail_supplier")
    p5 = snapshot_of(dataset, by_key, "dependent_supplier")
    assert debt_to_ebitda(p2["debt"], p2["ebitda"], p2["cash"]).value == D("2.5714")
    assert debt_to_ebitda(p5["debt"], p5["ebitda"], p5["cash"]).value == D("4.2000")
    for p in (p2, p5):
        assert p["cfads"] * 12 <= p["ebitda"]

    p4 = snapshot_of(dataset, by_key, "furniture_maker")
    assert max_loan_by_dscr(p4["cfads"], p4["debt_service"], D("0.235"), 36).value == D(
        "11290503.00"
    )


def test_simulators_per_section_9_3(dataset, by_key):
    sims = dataset["simulators"]

    def inn(code):
        return persona_company(dataset, by_key, code)["inn"]

    for code in REQUISITES:
        tb = sims["transparent_business"][inn(code)]
        assert tb == {
            "status": "ok",
            "data": {"mass_address": False, "mass_director": False, "tax_arrears": "0.00"},
        }
        egrul = sims["egrul"][inn(code)]
        assert egrul["data"]["registry_status"] == REQUISITES[code][6]
        assert egrul["data"]["director_name"] == DIRECTORS[code] + " (демо)"
        shares = sum(D(f["share"]) for f in egrul["data"]["founders"])
        assert shares == 1
        bki = sims["bki"][inn(code)]["data"]
        expected = (0, 10) if code == "furniture_maker" else (0, 0)
        assert (bki["current_overdue_days"], bki["past_overdue_max_days"]) == expected
        assert sims["bki"][inn(code)]["status"] == "ok"
    assert sims["egrul"][inn("liquidating_company")]["status"] == "warning"
    ip_founders = sims["egrul"][inn("coffee_shop")]["data"]["founders"]
    assert ip_founders == [
        {"name": "Лаврова Анна Сергеевна (демо)", "inn": inn("coffee_shop"), "share": "1.0000"}
    ]
    for code, debt in (("retail_supplier", "18600000"), ("dependent_supplier", "16800000")):
        obligations = sims["bki"][inn(code)]["data"]["obligations"]
        assert sum(D(o["balance"]) for o in obligations) == D(debt)


def test_users_and_memberships(dataset, by_key):
    users = by_key["user"]
    for code, persona in dataset["personas"].items():
        assert persona["application"] is None
        signatory = users[persona["users"][0]]
        assert signatory["username"] == f"demo_{code}" and signatory["_login_enabled"] is True
        assert signatory["profile"] == {
            "kind": "client", "full_name": DIRECTORS[code] + " (демо)", "is_demo": True,
        }  # fmt: skip
    maker = dataset["personas"]["furniture_maker"]["users"]
    assert [users[k]["username"] for k in maker] == ["demo_furniture_maker", "demo_accountant"]
    memberships = {(m["user"], m["company"]): m for m in dataset["memberships"]}
    accountant = memberships[("u_demo_accountant", "co_furniture_maker")]
    assert (accountant["role"], accountant["position"]) == ("preparer", "Главный бухгалтер")
    coffee = memberships[("u_coffee_shop", "co_coffee_shop")]
    assert (coffee["role"], coffee["position"]) == ("signatory", "Индивидуальный предприниматель")
    bank = [u for u in dataset["users"] if u["profile"]["kind"] == "bank"]
    assert [u["username"] for u in bank] == ["demo_bank", "demo_bank_2", "demo_bank_3"]
    assert all(u["_login_enabled"] for u in bank)
