"""
Conversation Memory - chat history store aur retrieve karo.
Multiple sessions support karta hai. Production mein Redis/DB se replace hoga.
"""

from __future__ import annotations

import time
import uuid
from collections import defaultdict, deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class MessageRole(str, Enum):
    """Chat message ke possible roles - OpenAI/Gemini compatible."""
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


@dataclass
class Message:
    """Ek single chat message - role + content + metadata."""
    role: MessageRole
    content: str
    timestamp: float = field(default_factory=time.time)
    metadata: dict[str, Any] = field(default_factory=dict)
    message_id: str = field(default_factory=lambda: str(uuid.uuid4()))

    def to_dict(self) -> dict[str, Any]:
        """LLM API ke liye dict format - OpenAI style."""
        return {
            "role": self.role.value,
            "content": self.content,
        }


class ConversationMemory:
    """
    In-memory conversation history manager.
    Per-session deque rakhta hai taake memory bounded rahe.

    Features:
    - Multi-session support
    - Token-aware trimming (optional)
    - Quick retrieval methods
    """

    def __init__(self, max_messages_per_session: int = 100) -> None:
        self._sessions: dict[str, deque[Message]] = defaultdict(
            lambda: deque(maxlen=max_messages_per_session)
        )
        self.max_messages_per_session = max_messages_per_session
        self._system_prompts: dict[str, str] = {}

    def add_message(
        self,
        role: MessageRole,
        content: str,
        session_id: str = "default",
        **metadata: Any,
    ) -> Message:
        """Naya message add karo - oldest auto-trim ho jayega agar limit cross ho."""
        msg = Message(role=role, content=content, metadata=metadata)
        self._sessions[session_id].append(msg)
        logger_msg = content[:80] if content else ""
        return msg

    def set_system_prompt(self, prompt: str, session_id: str = "default") -> None:
        """Session ke liye system prompt set karo - har LLM call mein shuru mein jata hai."""
        self._system_prompts[session_id] = prompt

    def get_history(self, session_id: str = "default") -> list[Message]:
        """Pure session ki history return karo (copy, so safe to iterate)."""
        return list(self._sessions.get(session_id, []))

    def get_recent(self, session_id: str = "default", limit: int = 10) -> list[Message]:
        """Last N messages return karo - recent context ke liye."""
        history = self._sessions.get(session_id, [])
        return list(history)[-limit:]

    def get_for_llm(self, session_id: str = "default") -> list[dict[str, Any]]:
        """
        LLM API ke liye formatted history.
        System prompt (agar set ho) + saare messages.
        """
        messages: list[dict[str, Any]] = []
        sys_prompt = self._system_prompts.get(session_id)
        if sys_prompt:
            messages.append({"role": MessageRole.SYSTEM.value, "content": sys_prompt})
        for msg in self._sessions.get(session_id, []):
            messages.append(msg.to_dict())
        return messages

    def clear_session(self, session_id: str) -> None:
        """Ek specific session ki history delete karo."""
        self._sessions.pop(session_id, None)
        self._system_prompts.pop(session_id, None)

    def clear_all(self) -> None:
        """Sab sessions ki history clear karo - testing ke liye useful."""
        self._sessions.clear()
        self._system_prompts.clear()

    def session_count(self) -> int:
        """Active sessions ki count return karo."""
        return len(self._sessions)

    def total_messages(self) -> int:
        """All sessions ke saare messages ki total count."""
        return sum(len(s) for s in self._sessions.values())
