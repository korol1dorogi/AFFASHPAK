"""Any OpenAI-compatible Chat Completions API (LLM_BASE_URL, LLM_API_KEY, LLM_MODEL)."""

import json
from typing import Any

from apps.assistant.llm.base import LLMError, LLMResponse, Message, ToolCall, ToolSpec


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
        if not model:
            raise LLMError("LLM_MODEL is not set")
        self._model = model
        if sdk_client is None:
            from openai import OpenAI

            if not api_key:
                raise LLMError("LLM_API_KEY is not set")
            sdk_client = OpenAI(base_url=base_url or None, api_key=api_key, timeout=timeout)
        self._client = sdk_client

    def complete(self, messages: list[Message], tools: list[ToolSpec]) -> LLMResponse:
        kwargs: dict[str, Any] = {
            "model": self._model,
            "messages": to_wire_messages(messages),
            "temperature": 0,
        }
        if tools:
            kwargs["tools"] = to_wire_tools(tools)
        try:
            completion = self._client.chat.completions.create(**kwargs)
        except Exception as exc:
            # Never leak request details (keys, user data) into the error text.
            raise LLMError(f"LLM request failed: {type(exc).__name__}") from exc
        return parse_completion(completion)
