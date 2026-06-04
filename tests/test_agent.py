"""
Tests for the ReACT loop core logic.
Yeh tests mock LLM use karte hain taake real API calls na hon.
"""

from __future__ import annotations

import pytest

from agent.core.react_loop import LoopStatus, ReACTConfig, ReACTLoop
from agent.core.state import AgentState, StateManager, StepType
from agent.llm.client import LLMProvider, LLMResponse, MockLLMClient
from agent.memory.conversation import ConversationMemory, MessageRole
from agent.tools.base import BaseTool, ToolResult
from agent.tools.registry import ToolRegistry


class DummyTool(BaseTool):
    """Test tool - input echo karta hai as observation."""

    @property
    def name(self) -> str:
        return "dummy"

    @property
    def description(self) -> str:
        return "A dummy tool for testing"

    async def run(self, tool_input: dict) -> ToolResult:
        return ToolResult(success=True, data={"echo": tool_input})


class TestAgentState:
    """AgentState unit tests."""

    def test_state_creation(self):
        state = AgentState(user_input="test")
        assert state.user_input == "test"
        assert state.current_iteration == 0
        assert state.steps == []
        assert state.observations == []

    def test_add_step(self):
        state = AgentState()
        state.add_step(StepType.THINK, "thinking...")
        assert len(state.steps) == 1
        assert state.steps[0].type == StepType.THINK

    def test_reset(self):
        state = AgentState(user_input="original")
        state.add_step(StepType.THINK, "x")
        state.reset()
        assert state.user_input == ""
        assert state.steps == []


class TestStateManager:
    """StateManager tests."""

    def test_create_and_retrieve(self):
        mgr = StateManager()
        state = mgr.create_state("input", session_id="s1")
        assert mgr.get_state("s1") is state

    def test_delete_state(self):
        mgr = StateManager()
        mgr.create_state("input", session_id="s1")
        mgr.delete_state("s1")
        assert mgr.get_state("s1") is None


class TestConversationMemory:
    """ConversationMemory tests."""

    def test_add_and_retrieve(self):
        mem = ConversationMemory()
        mem.add_message(MessageRole.USER, "hello", session_id="s1")
        history = mem.get_history("s1")
        assert len(history) == 1
        assert history[0].content == "hello"

    def test_session_isolation(self):
        mem = ConversationMemory()
        mem.add_message(MessageRole.USER, "a", session_id="s1")
        mem.add_message(MessageRole.USER, "b", session_id="s2")
        assert len(mem.get_history("s1")) == 1
        assert len(mem.get_history("s2")) == 1

    def test_clear_session(self):
        mem = ConversationMemory()
        mem.add_message(MessageRole.USER, "x", session_id="s1")
        mem.clear_session("s1")
        assert mem.get_history("s1") == []


class TestToolRegistry:
    """ToolRegistry tests."""

    def test_register_and_get(self):
        reg = ToolRegistry()
        reg.register(DummyTool())
        assert "dummy" in reg
        assert reg.get("dummy") is not None

    def test_unregister(self):
        reg = ToolRegistry()
        reg.register(DummyTool())
        reg.unregister("dummy")
        assert "dummy" not in reg

    def test_describe_all(self):
        reg = ToolRegistry()
        reg.register(DummyTool())
        descs = reg.describe_all()
        assert len(descs) == 1
        assert descs[0]["name"] == "dummy"


class TestReACTLoop:
    """ReACT loop integration tests with mock LLM."""

    @pytest.mark.asyncio
    async def test_simple_run(self):
        """Basic run with mock LLM - should complete without crashing."""
        llm = MockLLMClient(
            default_response='{"type": "final_answer", "answer": "test answer"}'
        )
        mem = ConversationMemory()
        reg = ToolRegistry()
        loop = ReACTLoop(llm, mem, reg, ReACTConfig(max_iterations=3))

        result = await loop.run("test question", session_id="s1")
        assert result.status == LoopStatus.SUCCESS
        assert "test answer" in result.final_answer

    @pytest.mark.asyncio
    async def test_max_iterations(self):
        """Agar LLM kabhi final_answer nahi de to max_iterations pe stop ho."""
        llm = MockLLMClient(
            default_response='{"type": "tool_call", "tool": "missing", "input": {}}'
        )
        mem = ConversationMemory()
        reg = ToolRegistry()
        reg.register(DummyTool())
        loop = ReACTLoop(llm, mem, reg, ReACTConfig(max_iterations=2, reflection_enabled=False))

        result = await loop.run("test", session_id="s1")
        assert result.status == LoopStatus.MAX_ITERATIONS


class TestCodeReviewAgent:
    """High-level CodeReviewAgent tests."""

    @pytest.mark.asyncio
    async def test_agent_initialization(self):
        from agent.agent import CodeReviewAgent

        llm = MockLLMClient()
        agent = CodeReviewAgent(llm)
        assert agent.llm is llm
        assert "dummy" not in agent.tool_registry

    @pytest.mark.asyncio
    async def test_register_and_review(self):
        from agent.agent import CodeReviewAgent

        llm = MockLLMClient(
            default_response='{"type": "final_answer", "answer": "looks good"}'
        )
        agent = CodeReviewAgent(llm)
        agent.register_tool(DummyTool())

        result = await agent.review("check this code", session_id="s1")
        assert result.status == LoopStatus.SUCCESS

    @pytest.mark.asyncio
    async def test_get_stats(self):
        from agent.agent import CodeReviewAgent

        agent = CodeReviewAgent(MockLLMClient())
        stats = agent.get_stats()
        assert "session_count" in stats
        assert "tool_count" in stats
