"""Test helpers: validate real API responses against docs/openapi.yaml (contract-first, D2)."""

import json
from functools import cache
from typing import Any

from django.conf import settings
from openapi_core import OpenAPI
from openapi_core.testing import MockRequest, MockResponse


@cache
def _spec() -> OpenAPI:
    return OpenAPI.from_file_path(str(settings.OPENAPI_SPEC_PATH))


def assert_matches_contract(
    response: Any,
    *,
    method: str,
    path: str,
    request_body: Any = None,
) -> None:
    """Raise if the response (status, headers, body) does not match the contract.

    `path` is the concrete URL path, e.g. "/api/applications/42".
    """
    request = MockRequest(
        "http://testserver",
        method.lower(),
        path,
        data=json.dumps(request_body) if request_body is not None else None,
        content_type="application/json",
    )
    content_type = response.get("Content-Type", "application/json").split(";")[0]
    mock_response = MockResponse(
        data=response.content,
        status_code=response.status_code,
        content_type=content_type,
    )
    _spec().validate_response(request, mock_response)
