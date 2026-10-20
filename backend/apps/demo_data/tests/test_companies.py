import re
from datetime import date
from functools import cache

from django.conf import settings
from openapi_core import OpenAPI

from apps.demo_data.build import DEFAULT_COMPANY_COUNT, SCHEMA_VERSION
from apps.demo_data.ids import DEMO_REGION_CODE, is_valid_inn, is_valid_ogrn
from apps.demo_data.personas import PERSONAS


@cache
def registry_record_schema() -> dict:
    """RegistryRecord from docs/openapi.yaml with $refs of its properties resolved."""
    spec = OpenAPI.from_file_path(str(settings.OPENAPI_SPEC_PATH)).spec
    schemas = spec / "components" / "schemas"
    record = schemas / "RegistryRecord"
    with record.open() as raw:
        required = list(raw["required"])
    properties = {}
    for name in required:
        with (record / "properties" / name).open() as prop:
            properties[name] = dict(prop)
    return {"required": required, "properties": properties}


def test_top_level(dataset):
    assert dataset["schema_version"] == SCHEMA_VERSION
    assert dataset["is_demo"] is True
    assert len(dataset["companies"]) == DEFAULT_COMPANY_COUNT + len(PERSONAS) >= 200


def test_every_inn_and_ogrn_is_valid_and_in_demo_region(dataset):
    for company in dataset["companies"]:
        inn, ogrn = company["inn"], company["ogrn"]
        assert is_valid_inn(inn), inn
        assert is_valid_ogrn(ogrn), ogrn
        assert inn[:2] == DEMO_REGION_CODE
        assert ogrn[3:5] == DEMO_REGION_CODE
        if company["legal_form"] == "ip":
            assert (len(inn), len(ogrn), ogrn[0]) == (12, 15, "3")
        else:
            assert (len(inn), len(ogrn), ogrn[0]) == (10, 13, "1")
        assert ogrn[1:3] == company["registered_at"][2:4]


def test_inns_are_unique(dataset):
    inns = [company["inn"] for company in dataset["companies"]]
    assert len(inns) == len(set(inns))


def test_both_legal_forms_present(dataset):
    assert {company["legal_form"] for company in dataset["companies"]} == {"ip", "ooo"}


def test_companies_match_registry_record_contract(dataset):
    schema = registry_record_schema()
    for company in dataset["companies"]:
        assert set(company) == {*schema["required"], "is_demo"}
        assert company["is_demo"] is True
        assert "(демо)" in company["name"]
        for name, prop in schema["properties"].items():
            value = company[name]
            assert isinstance(value, str), name
            if "pattern" in prop:
                assert re.fullmatch(prop["pattern"], value), (name, value)
            if "enum" in prop:
                assert value in prop["enum"], (name, value)
            if prop.get("format") == "date":
                date.fromisoformat(value)


def test_registration_dates_are_in_the_past(dataset):
    as_of = date.fromisoformat(dataset["as_of"])
    for company in dataset["companies"]:
        assert date.fromisoformat(company["registered_at"]) < as_of
