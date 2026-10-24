"""Registration UX: one password message at a time, in the order AUTH_PASSWORD_VALIDATORS
lists them — a pile of four complaints at once reads as noise."""

import pytest
from rest_framework.test import APIClient

from apps.core.testing import assert_matches_contract

pytestmark = pytest.mark.django_db
PATH = "/api/auth/register"


@pytest.mark.parametrize(
    ("password", "first"),
    [
        ("abc", "не менее 8"),  # short, also common: only «short» is said
        ("12345678", "только из цифр"),  # numeric, also common: only «numeric»
        ("qwerty123", "распространён"),
        ("kofeinia2024", "похож на имя пользователя"),
    ],
)
def test_one_message_at_a_time_in_priority_order(password, first):
    body = {"username": "kofeinia", "password": password, "full_name": "Ирина Демо"}
    response = APIClient().post(PATH, body, format="json")
    assert response.status_code == 400
    assert_matches_contract(response, method="post", path=PATH, request_body=body)
    messages = response.json()["error"]["details"]["password"]
    assert len(messages) == 1
    assert first in messages[0]
