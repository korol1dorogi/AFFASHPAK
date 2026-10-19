from django.core.exceptions import RequestDataTooBig
from django.http import Http404
from rest_framework import exceptions

from apps.core.exceptions import api_exception_handler


def test_not_found_uses_single_error_format():
    response = api_exception_handler(Http404(), {})

    assert response.status_code == 404
    assert response.data["error"]["code"] == "not_found"
    assert "details" not in response.data["error"]


def test_validation_error_keeps_field_details():
    response = api_exception_handler(
        exceptions.ValidationError({"amount": ["Обязательное поле."]}), {}
    )

    assert response.status_code == 400
    assert response.data["error"]["code"] == "invalid"
    assert response.data["error"]["details"] == {"amount": ["Обязательное поле."]}


def test_request_too_big_uses_413():
    response = api_exception_handler(RequestDataTooBig("too big"), {})

    assert response is not None
    assert response.status_code == 413
    assert response.data == {
        "error": {
            "code": "payload_too_large",
            "message": "Файл больше допустимого размера.",
        }
    }


def test_unknown_url_returns_json_error(client, settings):
    settings.DEBUG = False

    response = client.get("/api/does-not-exist")

    assert response.status_code == 404
    assert response.json() == {"error": {"code": "not_found", "message": "Не найдено."}}
