"""What the client (tools.py) and the bank (tools_bank.py) tool sets share (interface И3).

A tool takes the current user and the model's arguments and returns plain JSON. Arguments come
from the model, so they are untrusted: validated like a request body, an unknown argument is an
error. `run_registry` never raises on a bad call — the model gets `{"error": {code, message}}`
and can say what went wrong; the result goes as is into the journal (AssistantMessage.tool_calls).

Strings a person typed into the application (purpose, collateral, company name, answers) travel
in a separate `client_text` object: they are data, not instructions, and the guard layer
(`guards.for_model`, called by the engine for every tool result) wraps them as untrusted before
the model sees them (docs/redteam.md, attack 6 and attack-bank-indirect).
"""

from collections.abc import Callable
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from django.contrib.auth.models import AbstractBaseUser
from rest_framework import serializers
from rest_framework.exceptions import APIException, ValidationError

from apps.assistant.llm.base import ToolSpec


@dataclass(frozen=True)
class Tool:
    spec: ToolSpec
    run: Callable[[AbstractBaseUser, dict], dict]


def registry(*tools: Tool) -> dict[str, Tool]:
    return {tool.spec.name: tool for tool in tools}


def validated(serializer_class: type[serializers.Serializer], arguments: dict) -> dict:
    """additionalProperties: false — an unknown argument («status», «approved_amount»…) is an
    error, not silently ignored."""
    serializer = serializer_class(data=arguments)
    unknown = sorted(set(arguments) - set(serializer.fields))
    if unknown:
        raise ValidationError({name: ["Неизвестное поле."] for name in unknown})
    serializer.is_valid(raise_exception=True)
    return serializer.validated_data


def run_registry(tools: dict[str, Tool], user: AbstractBaseUser, name: str, arguments: Any) -> dict:
    """Run one tool of the set as `user`. Errors come back as data, never as an exception."""
    tool = tools.get(name)
    if tool is None:
        return error("unknown_tool", "Такого инструмента нет.")
    if not isinstance(arguments, dict):
        return error("invalid", "Аргументы должны быть объектом.")
    try:
        return tool.run(user, arguments)
    except ValidationError as exc:
        return {"error": {"code": "invalid", "message": "Проверьте данные.", "details": exc.detail}}
    except APIException as exc:
        codes = exc.get_codes()
        code = codes if isinstance(codes, str) else exc.default_code
        return error(code, str(exc.detail))


def error(code: str, message: str) -> dict:
    return {"error": {"code": code, "message": message}}


def money(value: Decimal | None) -> str | None:
    """Money and rates go out as plain decimal strings (`"900000.00"`, `"0.24"`), never floats."""
    return None if value is None else format(value, "f")


def client_text(**fields: str | None) -> dict[str, str]:
    """Text a person typed: only the filled fields, for the guard layer to wrap as untrusted."""
    return {name: value for name, value in fields.items() if value}


# ───────────────────────── argument schemas the tools share ─────────────────────────


class ApplicationRefSerializer(serializers.Serializer):
    """Client tools: the application is optional — not given, the user's latest one."""

    application_id = serializers.IntegerField(min_value=1, required=False)


class BankApplicationSerializer(serializers.Serializer):
    """Bank tools: the officer always names the application."""

    application_id = serializers.IntegerField(min_value=1)


APPLICATION_ID = {
    "application_id": {
        "type": "integer",
        "minimum": 1,
        "description": "Номер заявки. Не указан — последняя заявка пользователя.",
    }
}
BANK_APPLICATION_ID = {
    "type": "object",
    "required": ["application_id"],
    "additionalProperties": False,
    "properties": {
        "application_id": {"type": "integer", "minimum": 1, "description": "Номер заявки."}
    },
}
MONEY = {
    "type": "string",
    "pattern": r"^\d+(\.\d{1,2})?$",
    "description": "Рубли, например 900000.00",
}
