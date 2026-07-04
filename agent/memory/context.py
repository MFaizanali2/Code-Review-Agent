"""
Context Window Manager - LLM ke token limit ko manage karo.
Jab conversation lambi ho jaye to purane messages summarize ya trim karo.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from agent.memory.conversation import Message, MessageRole

logger = logging.getLogger(__name__)


@dataclass
class TokenBudget:
    """LLM ke context window ka budget - tokens mein."""
    total: int              # Model ka max context (e.g., 32000 for Gemini Pro)
    reserved_for_system: int = 500    # System prompt ke liye reserved
    reserved_for_response: int = 2000  # LLM ke response ke liye reserved
    safety_margin: int = 500         # Counting errors ke liye buffer

    @property
    def available(self) -> int:
        """Available tokens for conversation history."""
        return (
            self.total
            - self.reserved_for_system
            - self.reserved_for_response
            - self.safety_margin
        )


class ContextWindow:
    """
    Context window ko manage karne ka helper.
    Approximate token count use karta hai (1 token ~= 4 chars).
    Production mein tiktoken ya model-specific tokenizer use karna chahiye.
    """

    def __init__(self, budget: TokenBudget) -> None:
        self.budget = budget

    def estimate_tokens(self, text: str) -> int:
        """
        Token count estimate karo.
        Simple approximation - exact counting ke liye tokenizer integrate karna hoga.
        """
        if not text:
            return 0
        # Average 1 token per 4 characters for English; Roman Urdu thoda different
        return max(1, len(text) // 4)

    def total_tokens(self, messages: list[Message]) -> int:
        """Saari messages ke estimated tokens count karo."""
        return sum(self.estimate_tokens(m.content) for m in messages)

    def fit_to_budget(
        self, messages: list[Message], keep_system: bool = True
    ) -> list[Message]:
        """
        Messages ko budget mein fit karo.
        Strategy:
        1. System message hamesha rakhte hain
        2. Latest messages prioritize karte hain
        3. Beech ke messages skip karte hain agar zyada ho
        """
        if not messages:
            return messages

        if keep_system:
            system_msgs = [m for m in messages if m.role == MessageRole.SYSTEM]
            other_msgs = [m for m in messages if m.role != MessageRole.SYSTEM]
        else:
            system_msgs = []
            other_msgs = list(messages)

        available = self.budget.available
        used = self.estimate_tokens(" ".join(m.content for m in system_msgs))
        if used > available:
            logger.warning("System prompt exceeds budget: %d/%d", used, available)
            return []

        # Latest messages se peeche jaate hain aur add karte hain jab tak budget pura na ho
        fitted: list[Message] = []
        for msg in reversed(other_msgs):
            msg_tokens = self.estimate_tokens(msg.content)
            if used + msg_tokens > available:
                break
            fitted.insert(0, msg)
            used += msg_tokens

        logger.info("Context fit: kept %d/%d messages (%d/%d tokens)",
                    len(fitted), len(other_msgs), used, available)
        return system_msgs + fitted

    def needs_truncation(self, messages: list[Message]) -> bool:
        """Check karo ke kya truncation zaroori hai ya nahi."""
        return self.total_tokens(messages) > self.budget.available

    def get_stats(self, messages: list[Message]) -> dict[str, Any]:
        """Debug/UI ke liye context window stats."""
        used = self.total_tokens(messages)
        return {
            "total_tokens_estimated": used,
            "budget_available": self.budget.available,
            "utilization_percent": round(used / max(1, self.budget.available) * 100, 2),
            "message_count": len(messages),
            "needs_truncation": self.needs_truncation(messages),
        }
