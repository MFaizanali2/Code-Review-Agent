"""
LLM Client Interface - sab LLM providers ke liye unified contract.
Person 3 iske against Gemini aur OpenAI implementations banayega.
Agent sirf is interface ke through LLM se baat karega.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class LLMProvider(str, Enum):
    """Supported LLM providers."""
    GEMINI = "gemini"
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    MOCK = "mock"  # Testing ke liye


@dataclass
class LLMResponse:
    """
    LLM se mila response - standardized format.
    Provider-agnostic - sab providers se same shape mein response aata hai.
    """
    content: str
    provider: LLMProvider
    model: str
    usage: dict[str, int] = field(default_factory=dict)
    finish_reason: str = "stop"
    raw: Any = None  # Original provider response (debugging ke liye)
    latency_ms: float = 0.0

    @property
    def total_tokens(self) -> int:
        """Total tokens used (input + output)."""
        return self.usage.get("total_tokens", 0)


class LLMClient(ABC):
    """
    Abstract LLM client.
    Provider-specific clients (GeminiClient, OpenAIClient) isko inherit karengi.
    Agent ko sirf is interface ki zarurat hai.
    """

    provider: LLMProvider

    @abstractmethod
    async def generate(
        self,
        prompt: str,
        system: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
        **kwargs: Any,
    ) -> LLMResponse:
        """
        Simple generation - ek prompt lo, response do.
        Single turn ke liye.
        """
        ...

    @abstractmethod
    async def chat(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 2048,
        **kwargs: Any,
    ) -> LLMResponse:
        """
        Multi-turn chat.
        messages format: [{"role": "user|assistant|system", "content": "..."}]
        """
        ...

    @abstractmethod
    async def generate_with_tools(
        self,
        prompt: str,
        tools: list[dict[str, Any]],
        system: str | None = None,
        temperature: float = 0.3,
        **kwargs: Any,
    ) -> LLMResponse:
        """
        Function calling / tool use ke saath generation.
        tools format: OpenAI-style function definitions.
        """
        ...

    def estimate_cost(self, response: LLMResponse) -> float:
        """
        Response ka approximate cost calculate karo.
        Default implementation - subclasses override karke exact pricing den.
        Returns cost in USD.
        """
        return 0.0


class MockLLMClient(LLMClient):
    """
    Testing ke liye mock LLM client.
    Real API call nahi karta - predefined responses deta hai.
    """

    provider = LLMProvider.MOCK

    def __init__(self, default_response: str = "Mock response") -> None:
        self.default_response = default_response
        self.call_count = 0

    async def generate(
        self, prompt: str, system: str | None = None, **kwargs: Any
    ) -> LLMResponse:
        self.call_count += 1
        return LLMResponse(
            content=self.default_response,
            provider=LLMProvider.MOCK,
            model="mock-model",
            usage={"total_tokens": 10},
        )

    async def chat(
        self, messages: list[dict[str, str]], **kwargs: Any
    ) -> LLMResponse:
        return await self.generate("")

    async def generate_with_tools(
        self, prompt: str, tools: list[dict[str, Any]], **kwargs: Any
    ) -> LLMResponse:
        return await self.generate(prompt)
