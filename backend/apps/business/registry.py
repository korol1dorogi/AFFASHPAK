"""ЕГРЮЛ/ЕГРИП lookup by INN (RegistryRecord in docs/openapi.yaml).

Until the simulator service (S1) exists, answers come in-process from the same synthetic
generator S1 will serve (apps/demo_data, S2): deterministic by INN, all marked «демо».
When S1 lands, only `_records` changes to an HTTP call that raises SourceUnavailable.
"""

from functools import cache

from apps.demo_data.build import generate

RECORD_FIELDS = (
    "inn",
    "ogrn",
    "legal_form",
    "name",
    "okved",
    "okved_name",
    "registered_at",
    "region",
    "address",
    "registry_status",
    "director_name",
)


@cache
def _records() -> dict[str, dict]:
    data = generate()
    egrul = data["simulators"]["egrul"]
    return {
        company["inn"]: {field: company[field] for field in RECORD_FIELDS}
        for company in data["companies"]
        if company["inn"] in egrul
    }


def lookup(inn: str) -> dict | None:
    """The registry record, or None when the INN is not in the registry."""
    record = _records().get(inn)
    return dict(record) if record is not None else None
