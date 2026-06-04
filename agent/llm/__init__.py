"""
LLM package - Gemini/OpenAI ke liye unified interface.
Person 3 is package ke andar actual provider implementations add karega.
Agent sirf is interface ke through LLM se baat karega - decoupling ke liye.
"""

from agent.llm.client import LLMClient, LLMResponse, LLMProvider

__all__ = ["LLMClient", "LLMResponse", "LLMProvider"]
