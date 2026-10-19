from django.conf import settings

from apps.assistant.llm.base import (
    LLMClient,
    LLMError,
    LLMResponse,
    Message,
    ToolCall,
    ToolSpec,
)
from apps.assistant.llm.mock import MockLLMClient
from apps.assistant.llm.openai_compat import OpenAICompatibleClient

__all__ = [
    "LLMClient",
    "LLMError",
    "LLMResponse",
    "Message",
    "MockLLMClient",
    "OpenAICompatibleClient",
    "ToolCall",
    "ToolSpec",
    "get_llm_client",
]


def get_llm_client() -> LLMClient:
    """Provider from LLM_PROVIDER: "mock" (default) or "openai" (any compatible API)."""
    provider = settings.LLM_PROVIDER
    if provider == "mock":
        return MockLLMClient()
    if provider == "openai":
        return OpenAICompatibleClient(
            base_url=settings.LLM_BASE_URL,
            api_key=settings.LLM_API_KEY,
            model=settings.LLM_MODEL,
            timeout=settings.LLM_TIMEOUT_SECONDS,
        )
    raise LLMError(f"Unknown LLM_PROVIDER: {provider!r} (expected 'mock' or 'openai')")
