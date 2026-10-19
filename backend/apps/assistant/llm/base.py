"""Provider-neutral LLM interface for the assistant.

The assistant never computes money itself: the model only chooses tools (recommendations,
calculator, application drafts) that run through the service layer as the current user.
"""

from dataclasses import dataclass, field
from typing import Any, Literal, Protocol

Role = Literal["system", "user", "assistant", "tool"]


@dataclass(frozen=True)
class ToolCall:
    id: str
    name: str
    arguments: dict[str, Any]


@dataclass(frozen=True)
class Message:
    role: Role
    content: str = ""
    tool_calls: tuple[ToolCall, ...] = ()
    tool_call_id: str | None = None  # for role="tool": which call this result answers


@dataclass(frozen=True)
class ToolSpec:
    """A tool the model may call. `parameters` is a JSON Schema object."""

    name: str
    description: str
    parameters: dict[str, Any] = field(default_factory=lambda: {"type": "object", "properties": {}})


@dataclass(frozen=True)
class LLMResponse:
    content: str
    tool_calls: tuple[ToolCall, ...] = ()


class LLMError(Exception):
    """Provider failed (network, auth, malformed answer). Message is safe to log."""


class LLMClient(Protocol):
    def complete(self, messages: list[Message], tools: list[ToolSpec]) -> LLMResponse: ...
