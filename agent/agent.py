"""
Main Agent Class - sab components ka integration point.
Yeh class high-level API provide karti hai jo API layer (Person 4) aur
frontend (Person 5) use karenge.

Architecture:
    User -> CodeReviewAgent -> ReACTLoop -> LLMClient
                                          -> ToolRegistry -> Tools (Person 2)
                                          -> ConversationMemory
                                          -> StateManager
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

from agent.core.orchestrator import ToolOrchestrator
from agent.core.react_loop import LoopResult, ReACTConfig, ReACTLoop
from agent.core.state import AgentState, StateManager
from agent.llm.client import LLMClient
from agent.memory.conversation import ConversationMemory, MessageRole
from agent.memory.context import ContextWindow, TokenBudget
from agent.prompts.system import SYSTEM_PROMPT
from agent.tools.base import BaseTool
from agent.tools.registry import ToolRegistry

logger = logging.getLogger(__name__)


class CodeReviewAgent:
    """
    High-level agent class - single entry point for all agent operations.

    Yeh class sab components ko wire karti hai:
    - LLM (Person 3 ka kaam)
    - Tools (Person 2 ka kaam)
    - Memory & State (Person 1 ka kaam)
    - ReACT loop (Person 1 ka kaam)

    Usage:
        agent = CodeReviewAgent(llm=my_llm)
        agent.register_tool(MyTool())
        result = await agent.review("check this code", session_id="user_123")
    """

    def __init__(
        self,
        llm: LLMClient,
        config: ReACTConfig | None = None,
        token_budget: TokenBudget | None = None,
        auto_load_tools: bool = True,
        skip_team_project: bool = False,
    ) -> None:
        # LLM client - Person 3 provide karega
        self.llm = llm

        # Memory aur state - Person 1 ka kaam
        self.memory = ConversationMemory(max_messages_per_session=100)
        self.state_manager = StateManager()
        self.context_window = ContextWindow(
            token_budget or TokenBudget(total=32000)
        )

        # Tool system - Person 2 tools register karega
        self.tool_registry = ToolRegistry()

        # Auto-load built-in tools unless disabled
        if auto_load_tools:
            from agent.tools.loader import load_builtin_tools

            load_builtin_tools(
                self.tool_registry, skip_team_project=skip_team_project
            )
            loaded = len(self.tool_registry)
            if loaded:
                logger.info("Auto-loaded %d built-in tools", loaded)

        self.orchestrator = ToolOrchestrator(self.tool_registry, max_parallel=3)

        # ReACT engine - core reasoning
        self.config = config or ReACTConfig()
        self.react_loop = ReACTLoop(
            llm=self.llm,
            memory=self.memory,
            registry=self.tool_registry,
            config=self.config,
        )

        # System prompt set karo default session ke liye
        self.memory.set_system_prompt(SYSTEM_PROMPT, session_id="default")
        logger.info("CodeReviewAgent initialized")

    def register_tool(self, tool: BaseTool) -> None:
        """Register a single tool with the tool registry."""
        self.tool_registry.register(tool)

    def register_tools(self, tools: list[BaseTool]) -> None:
        """Bulk tool registration."""
        self.tool_registry.register_many(tools)

    async def review(
        self,
        code_or_question: str,
        session_id: str | None = None,
        context: dict[str, Any] | None = None,
    ) -> LoopResult:
        """
        Main entry point - code review ya general question process karo.

        Args:
            code_or_question: User ka input - code snippet ya sawaal
            session_id: Conversation continue karne ke liye session ID
            context: Extra context (file path, language, etc.)

        Returns:
            LoopResult with final answer, status, and metadata
        """
        session_id = session_id or str(uuid.uuid4())
        logger.info("Review request: session=%s, input_len=%d",
                    session_id, len(code_or_question))

        # Context ko user input mein prepend karo agar diya ho
        full_input = self._build_full_input(code_or_question, context)

        # State banao/refresh karo
        self.state_manager.create_state(full_input, session_id=session_id)

        # ReACT loop chalao
        result = await self.react_loop.run(full_input, session_id=session_id)

        # Final state update karo
        state = self.state_manager.get_state(session_id)
        if state:
            state.final_answer = result.final_answer
            state.error = result.error

        logger.info(
            "Review done: session=%s, status=%s, iterations=%d, duration=%.2fs",
            session_id, result.status, result.iterations_used, result.duration_seconds,
        )
        return result

    async def chat(
        self,
        message: str,
        session_id: str | None = None,
    ) -> LoopResult:
        """
        Simple chat - ReACT ke bina direct memory se baat karo.
        Lightweight conversations ke liye useful.
        """
        from agent.core.react_loop import LoopStatus

        session_id = session_id or str(uuid.uuid4())
        self.memory.add_message(MessageRole.USER, message, session_id=session_id)
        messages = self.memory.get_for_llm(session_id)
        response = await self.llm.chat(messages)
        self.memory.add_message(MessageRole.ASSISTANT, response.content, session_id=session_id)
        return LoopResult(
            status=LoopStatus.SUCCESS,
            final_answer=response.content,
            iterations_used=1,
        )

    def get_session_history(self, session_id: str) -> list[dict[str, Any]]:
        """Session ki poori history dekho - frontend ke liye useful."""
        history = self.memory.get_history(session_id)
        return [
            {
                "role": msg.role.value,
                "content": msg.content,
                "timestamp": msg.timestamp,
            }
            for msg in history
        ]

    def get_session_state(self, session_id: str) -> AgentState | None:
        """Session ka current state retrieve karo."""
        return self.state_manager.get_state(session_id)

    def clear_session(self, session_id: str) -> None:
        """Session ki memory aur state clear karo."""
        self.memory.clear_session(session_id)
        self.state_manager.delete_state(session_id)

    def get_stats(self) -> dict[str, Any]:
        """
        Agent ke current stats return karo - health check / monitoring ke liye.
        """
        return {
            "active_sessions": self.state_manager.list_sessions(),
            "session_count": self.memory.session_count(),
            "total_messages": self.memory.total_messages(),
            "registered_tools": self.tool_registry.list_names(),
            "tool_count": len(self.tool_registry),
        }

    def _build_full_input(
        self, user_input: str, context: dict[str, Any] | None
    ) -> str:
        """
        Context ko user input mein merge karo.
        Tool calls mein structured data pass karne ke liye useful.
        """
        if not context:
            return user_input
        ctx_parts = [f"{k}: {v}" for k, v in context.items()]
        ctx_str = "\n".join(ctx_parts)
        return f"Context:\n{ctx_str}\n\nRequest:\n{user_input}"
