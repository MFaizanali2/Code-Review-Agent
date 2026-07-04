"""Compatibility re-exports for agent.llm.client imports.

Keeps backward compatibility while code migrates to backend.llm.
"""

from backend.llm.llm_client import LLMClient, MockLLMClient
from backend.llm.llm_types import LLMResponse, Provider as LLMProvider

__all__ = ["LLMClient", "LLMResponse", "LLMProvider", "MockLLMClient"]
