"""SRC8: every simulator answer matches its contract in docs/external/*.yaml.

The contracts are what S1 will serve over HTTP, so the answers are checked as JSON — dates and
decimals as strings, the same normalisation the pipeline stores in Check.data.
"""

import json
from functools import cache

import pytest
from django.conf import settings
from openapi_core import OpenAPI
from openapi_core.testing import MockRequest, MockResponse

from apps.integrations import adapters
from apps.integrations.simulator_data import dataset

SOURCES = ("egrul", "transparent_business", "bki", "bank_account")
# Written by the adapter itself, never answered by a source: the source did not answer or was
# not asked (no consent). The contracts describe them as 503 / no request.
ADAPTER_ONLY = {"unavailable", "consent_missing"}


@cache
def _contract(source: str) -> OpenAPI:
    path = settings.OPENAPI_SPEC_PATH.parent / "external" / f"{source}.yaml"
    return OpenAPI.from_file_path(str(path))


def _validate(source: str, inn: str, answer: dict) -> None:
    body = json.dumps({"status": answer["status"], "data": answer["data"]}, default=str)
    request = MockRequest("http://simulator", "get", f"/{source}/{inn}")
    response = MockResponse(data=body.encode(), status_code=200, content_type="application/json")
    _contract(source).validate_response(request, response)


def _generated() -> list[tuple[str, str, dict]]:
    """Every answer of the synthetic world: the simulator tables and the edge cases."""
    data = dataset()
    answers = [
        (source, inn, answer)
        for source, table in data["simulators"].items()
        for inn, answer in table.items()
    ]
    for case in data["edge_cases"]:
        for source, answer in case["checks"].items():
            if answer["status"] not in ADAPTER_ONLY:
                answers.append((source, case["company"]["inn"], answer))
    return answers


@pytest.mark.parametrize("source", SOURCES)
def test_the_contract_is_valid_openapi(source):
    assert _contract(source).spec["paths"]


def test_every_generated_answer_matches_its_contract():
    answers = _generated()
    # All three simulator tables are in, and the edge cases add the bank account.
    assert {source for source, _, _ in answers} == set(SOURCES)
    assert len(answers) > 700
    for source, inn, answer in answers:
        try:
            _validate(source, inn, answer)
        except Exception as error:  # name the answer: one of ~800
            raise AssertionError(f"{source} {inn}: {error}") from error


@pytest.mark.parametrize(
    ("source", "answer"),
    [
        ("egrul", adapters.NOT_IN_REGISTRY),
        ("bki", {"status": "restricted", "data": {}}),
        ("bank_account", {"status": "ok", "data": {"months": 18}}),
    ],
)
def test_answers_the_synthetic_tables_do_not_have_match_too(source, answer):
    """«No such INN», hidden data and the bank account answer the adapter builds itself."""
    _validate(source, "000100000170", answer)


@pytest.mark.parametrize("source", SOURCES)
def test_the_examples_in_the_contract_match_it(source):
    """The examples are what a reader copies: they must be valid answers too."""
    operation = _contract(source).spec / "paths" / f"/{source}/{{inn}}" / "get"
    with (operation / "responses" / "200" / "content" / "application/json").open() as content:
        examples = {name: example["value"] for name, example in content["examples"].items()}
    assert examples
    for name, value in examples.items():
        try:
            _validate(source, "000100000170", value)
        except Exception as error:
            raise AssertionError(f"{source} example {name}: {error}") from error


def test_an_unknown_key_breaks_the_contract():
    """additionalProperties: false — a new key in the simulator must come with the contract."""
    answer = dataset()["simulators"]["egrul"]["000100000170"]
    changed = {**answer, "data": {**answer["data"], "rating": "AAA"}}
    with pytest.raises(Exception, match="rating"):
        _validate("egrul", "000100000170", changed)


def test_a_status_the_source_never_gives_breaks_the_contract():
    with pytest.raises(Exception):  # noqa: B017 - openapi-core raises its own invalid-data error
        _validate("bki", "000100000170", {"status": "consent_missing", "data": {}})
