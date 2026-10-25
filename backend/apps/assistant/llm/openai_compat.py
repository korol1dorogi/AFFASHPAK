"""Any OpenAI-compatible Chat Completions API (LLM_BASE_URL, LLM_API_KEY, LLM_MODEL).

LLM_MODEL may list several models with open weights, comma separated
(`qwen/qwen3.8-27b,openai/gpt-oss-20b`): a model that hits its rate limit (429), times out or
fails on the provider's side is skipped at once — no waiting inside the request — and stays
skipped until its `retry-after` passes. Free tiers give each model its own tokens-per-minute
budget, so the list multiplies how many turns per minute the assistant serves. All models
failing is an LLMError: the engine answers with the mock and says so honestly.
"""

import json
import logging
import time
from typing import Any

from apps.assistant.llm.base import LLMError, LLMResponse, Message, ToolCall, ToolSpec

logger = logging.getLogger(__name__)

DEFAULT_COOLDOWN_SECONDS = 30.0
MAX_COOLDOWN_SECONDS = 120.0
# Model → monotonic time until which it is skipped (per process; shared by every request).
_cooldown: dict[str, float] = {}


def to_wire_messages(messages: list[Message]) -> list[dict[str, Any]]:
    wire: list[dict[str, Any]] = []
    for message in messages:
        item: dict[str, Any] = {"role": message.role, "content": message.content}
        if message.tool_calls:
            item["tool_calls"] = [
                {
                    "id": call.id,
                    "type": "function",
                    "function": {
                        "name": call.name,
                        "arguments": json.dumps(call.arguments, ensure_ascii=False),
                    },
                }
                for call in message.tool_calls
            ]
        if message.tool_call_id:
            item["tool_call_id"] = message.tool_call_id
        wire.append(item)
    return wire


def to_wire_tools(tools: list[ToolSpec]) -> list[dict[str, Any]]:
    return [
        {
            "type": "function",
            "function": {
                "name": tool.name,
                "description": tool.description,
                "parameters": tool.parameters,
            },
        }
        for tool in tools
    ]


def parse_completion(completion: Any) -> LLMResponse:
    try:
        message = completion.choices[0].message
    except (AttributeError, IndexError) as exc:
        raise LLMError("LLM returned no choices") from exc

    calls: list[ToolCall] = []
    for call in message.tool_calls or []:
        try:
            arguments = json.loads(call.function.arguments or "{}")
        except json.JSONDecodeError as exc:
            raise LLMError(f"LLM returned invalid JSON arguments for {call.function.name}") from exc
        if not isinstance(arguments, dict):
            raise LLMError(f"LLM arguments for {call.function.name} must be an object")
        calls.append(ToolCall(id=call.id, name=call.function.name, arguments=arguments))
    return LLMResponse(content=message.content or "", tool_calls=tuple(calls))


def parse_models(value: str) -> list[str]:
    return [model.strip() for model in (value or "").split(",") if model.strip()]


def _retry_after(exc: Exception) -> float:
    """Seconds the provider asked to wait (header `retry-after`), within sane bounds."""
    response = getattr(exc, "response", None)
    headers = getattr(response, "headers", None) or {}
    try:
        seconds = float(headers.get("retry-after") or DEFAULT_COOLDOWN_SECONDS)
    except (TypeError, ValueError):
        seconds = DEFAULT_COOLDOWN_SECONDS
    return min(max(seconds, 1.0), MAX_COOLDOWN_SECONDS)


def _skippable(exc: Exception) -> bool:
    """Rate limit, timeout, connection or a 5xx — another model may answer. A 4xx of our own
    request (bad schema, unknown model, auth) would fail on every model the same way."""
    status = getattr(exc, "status_code", None)
    if status is None:
        return type(exc).__name__ in {"APITimeoutError", "APIConnectionError", "TimeoutError"}
    return status == 429 or status >= 500


class OpenAICompatibleClient:
    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        model: str,
        timeout: float = 30,
        sdk_client: Any = None,
    ) -> None:
        self._models = parse_models(model)
        if not self._models:
            raise LLMError("LLM_MODEL is not set")
        if sdk_client is None:
            from openai import OpenAI

            if not api_key:
                raise LLMError("LLM_API_KEY is not set")
            # No retries inside the SDK: waiting 30 s on a 429 is worse than the next model.
            sdk_client = OpenAI(
                base_url=base_url or None, api_key=api_key, timeout=timeout, max_retries=0
            )
        self._client = sdk_client

    def complete(self, messages: list[Message], tools: list[ToolSpec]) -> LLMResponse:
        now = time.monotonic()
        ready = [model for model in self._models if _cooldown.get(model, 0.0) <= now]
        # All cooling down: try the one that frees first rather than fail without asking.
        order = ready or sorted(self._models, key=lambda model: _cooldown.get(model, 0.0))[:1]
        last_error: Exception | None = None
        for model in order:
            kwargs: dict[str, Any] = {
                "model": model,
                "messages": to_wire_messages(messages),
                "temperature": 0,
            }
            if tools:
                kwargs["tools"] = to_wire_tools(tools)
            try:
                completion = self._client.chat.completions.create(**kwargs)
            except Exception as exc:
                last_error = exc
                if _skippable(exc):
                    _cooldown[model] = time.monotonic() + _retry_after(exc)
                    logger.warning(
                        "LLM model %s unavailable (%s), trying the next one", model,
                        type(exc).__name__,
                    )  # fmt: skip
                    continue
                # Never leak request details (keys, user data) into the error text.
                raise LLMError(f"LLM request failed: {type(exc).__name__}") from exc
            _cooldown.pop(model, None)
            return parse_completion(completion)
        name = type(last_error).__name__ if last_error else "no model"
        raise LLMError(f"LLM request failed on every model: {name}") from last_error
