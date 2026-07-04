"""
test_agent_modern.py - Comprehensive tests for modern agent components.
Covers agent types, conversation memory, agent state, ReACT loop,
and the modern CodeReviewAgent.

Run with:
    pytest tests/test_agent_modern.py -v
"""

from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any

import pytest

from agent.agent import CodeReviewAgent
from agent.agent_types import (
    AgentStatus,
    AgentStep,
    ReviewRequest,
    ReviewResult,
    StepType,
    ToolCall,
    ToolResult as AgentToolResult,
)
from agent.core.orchestrator import OrchestrationResult, ToolOrchestrator
from agent.core.react_loop import LoopResult, LoopStatus, ReACTConfig, ReACTLoop
from agent.core.state import AgentState, StateManager, StepType as StateStepType
from agent.llm.client import LLMProvider, LLMResponse, MockLLMClient
from agent.memory.conversation import ConversationMemory, MessageRole
from agent.tools.base import BaseTool, ToolResult, ToolSchema
from agent.tools.registry import ToolRegistry


# =============================================================================
# HELPER TOOLS
# =============================================================================

class SimpleTool(BaseTool):
    """A simple working tool for tests."""

    @property
    def name(self) -> str:
        return "simple_tool"

    @property
    def description(self) -> str:
        return "A simple test tool"

    async def run(self, tool_input: dict[str, Any]) -> ToolResult:
        return ToolResult(success=True, data={"value": tool_input.get("key", "default")})


class FailingTool(BaseTool):
    """A tool that always fails."""

    @property
    def name(self) -> str:
        return "failing_tool"

    @property
    def description(self) -> str:
        return "Always fails"

    async def run(self, tool_input: dict[str, Any]) -> ToolResult:
        return ToolResult(success=False, data={}, error="Intentional failure")


class CrashingTool(BaseTool):
    """A tool that raises an exception."""

    @property
    def name(self) -> str:
        return "crashing_tool"

    @property
    def description(self) -> str:
        return "Always crashes"

    async def run(self, tool_input: dict[str, Any]) -> ToolResult:
        raise RuntimeError("Simulated crash")


def make_registry() -> ToolRegistry:
    """Create registry with test tools."""
    r = ToolRegistry()
    r.register(SimpleTool())
    r.register(FailingTool())
    r.register(CrashingTool())
    return r


# =============================================================================
# TEST: AGENT TYPES (from agent/agent_types.py)
# =============================================================================

class TestAgentTypes:
    """Tests for agent_types.py dataclasses and enums."""

    def test_step_type_enum_values(self):
        assert StepType.THINK.value == "think"
        assert StepType.ACT.value == "act"
        assert StepType.OBSERVE.value == "observe"
        assert StepType.REFLECT.value == "reflect"
        assert len(list(StepType)) == 4

    def test_agent_status_enum_values(self):
        statuses = [s.value for s in AgentStatus]
        assert "idle" in statuses
        assert "thinking" in statuses
        assert "acting" in statuses
        assert "observing" in statuses
        assert "reflecting" in statuses
        assert "completed" in statuses
        assert "failed" in statuses

    def test_tool_call_creation(self):
        before = datetime.now(timezone.utc)
        call = ToolCall(tool_name="pylint", params={"file": "main.py"})
        after = datetime.now(timezone.utc)
        assert call.tool_name == "pylint"
        assert call.params == {"file": "main.py"}
        assert before <= call.timestamp <= after
        assert call.call_id is not None
        assert len(call.call_id) > 0

    def test_tool_call_empty_params(self):
        call = ToolCall(tool_name="simple")
        assert call.params == {}
        assert isinstance(call.params, dict)

    def test_tool_result_success(self):
        result = AgentToolResult(
            tool_name="pylint",
            success=True,
            data={"issues": 3},
            execution_time=1.5,
        )
        assert result.success is True
        assert result.data == {"issues": 3}
        assert result.error is None
        assert result.execution_time == 1.5

    def test_tool_result_failure(self):
        result = AgentToolResult(
            tool_name="bandit",
            success=False,
            data={},
            error="Connection timeout",
            execution_time=30.0,
        )
        assert result.success is False
        assert result.error == "Connection timeout"

    def test_agent_step_creation(self):
        before = datetime.now(timezone.utc)
        step = AgentStep(
            step_number=1,
            step_type=StepType.THINK,
            thought="Need to analyze",
            action=ToolCall(tool_name="pylint", params={}),
            reflection="All good",
        )
        after = datetime.now(timezone.utc)
        assert step.step_number == 1
        assert step.step_type == StepType.THINK
        assert step.thought == "Need to analyze"
        assert step.action is not None
        assert step.action.tool_name == "pylint"
        assert step.reflection == "All good"
        assert before <= step.timestamp <= after

    def test_agent_step_optional_fields(self):
        step = AgentStep(step_number=5, step_type=StepType.ACT)
        assert step.thought is None
        assert step.action is None
        assert step.observation is None
        assert step.reflection is None

    def test_review_request_defaults(self):
        before = datetime.now(timezone.utc)
        req = ReviewRequest(github_url="https://github.com/user/repo")
        after = datetime.now(timezone.utc)
        assert req.github_url == "https://github.com/user/repo"
        assert req.code_content is None
        assert req.analysis_type == "full"
        assert req.request_time is not None
        assert before <= req.request_time <= after
        assert req.request_id is not None

    def test_review_request_with_code(self):
        req = ReviewRequest(code_content="def foo(): pass", analysis_type="security")
        assert req.code_content == "def foo(): pass"
        assert req.github_url is None
        assert req.analysis_type == "security"

    def test_review_request_has_source(self):
        assert ReviewRequest(github_url="https://github.com/x/y").has_source() is True
        assert ReviewRequest(code_content="x").has_source() is True
        assert ReviewRequest().has_source() is False

    def test_review_result_creation(self):
        result = ReviewResult(
            success=True,
            quality_score=8.5,
            issues=[{"severity": "low", "title": "test"}],
            report="# Report\n\nAll good",
            steps_taken=5,
            execution_time=12.3,
        )
        assert result.success is True
        assert result.quality_score == 8.5
        assert len(result.issues) == 1
        assert result.report.startswith("# Report")
        assert result.steps_taken == 5
        assert result.execution_time == 12.3
        assert result.errors is None

    def test_review_result_to_dict(self):
        result = ReviewResult(
            success=True,
            quality_score=7.0,
            issues=[],
            report="test",
            steps_taken=3,
            execution_time=5.0,
        )
        d = result.to_dict()
        assert isinstance(d, dict)
        assert d["success"] is True
        assert d["quality_score"] == 7.0
        assert d["steps_taken"] == 3
        assert "timestamp" in d


# =============================================================================
# TEST: CONVERSATION MEMORY (from agent/memory/conversation.py)
# =============================================================================

class TestConversationMemory:
    """Tests for ConversationMemory."""

    def test_initial_state(self):
        mem = ConversationMemory()
        assert mem.session_count() == 0
        assert mem.total_messages() == 0

    def test_add_message(self):
        mem = ConversationMemory()
        msg = mem.add_message(MessageRole.USER, "Hello", session_id="s1")
        assert msg.role == MessageRole.USER
        assert msg.content == "Hello"
        assert mem.session_count() == 1
        assert mem.total_messages() == 1

    def test_add_multiple_messages(self):
        mem = ConversationMemory()
        mem.add_message(MessageRole.USER, "Hi", session_id="s1")
        mem.add_message(MessageRole.ASSISTANT, "Hello!", session_id="s1")
        assert mem.total_messages() == 2
        history = mem.get_history("s1")
        assert len(history) == 2
        assert history[0].role == MessageRole.USER
        assert history[1].role == MessageRole.ASSISTANT

    def test_system_prompt_prepended(self):
        mem = ConversationMemory()
        mem.set_system_prompt("You are a helpful assistant.", session_id="s1")
        mem.add_message(MessageRole.USER, "Hi", session_id="s1")
        messages = mem.get_for_llm("s1")
        assert len(messages) == 2
        assert messages[0]["role"] == "system"
        assert messages[0]["content"] == "You are a helpful assistant."
        assert messages[1]["role"] == "user"

    def test_get_for_llm_no_system_prompt(self):
        mem = ConversationMemory()
        mem.add_message(MessageRole.USER, "Hi", session_id="s1")
        messages = mem.get_for_llm("s1")
        assert len(messages) == 1
        assert messages[0]["role"] == "user"

    def test_get_recent(self):
        mem = ConversationMemory()
        for i in range(10):
            mem.add_message(MessageRole.USER, f"msg {i}", session_id="s1")
        recent = mem.get_recent("s1", limit=3)
        assert len(recent) == 3
        assert recent[0].content == "msg 7"
        assert recent[2].content == "msg 9"

    def test_multiple_sessions(self):
        mem = ConversationMemory()
        mem.add_message(MessageRole.USER, "A", session_id="s1")
        mem.add_message(MessageRole.USER, "B", session_id="s2")
        assert mem.session_count() == 2
        assert len(mem.get_history("s1")) == 1
        assert len(mem.get_history("s2")) == 1

    def test_clear_session(self):
        mem = ConversationMemory()
        mem.add_message(MessageRole.USER, "Hi", session_id="s1")
        assert mem.session_count() == 1
        mem.clear_session("s1")
        assert mem.session_count() == 0
        assert mem.get_history("s1") == []

    def test_clear_all(self):
        mem = ConversationMemory()
        mem.add_message(MessageRole.USER, "A", session_id="s1")
        mem.add_message(MessageRole.USER, "B", session_id="s2")
        mem.clear_all()
        assert mem.session_count() == 0
        assert mem.total_messages() == 0

    def test_max_messages_per_session(self):
        mem = ConversationMemory(max_messages_per_session=3)
        for i in range(10):
            mem.add_message(MessageRole.USER, f"msg {i}", session_id="s1")
        assert mem.total_messages() == 3
        history = mem.get_history("s1")
        assert history[0].content == "msg 7"

    def test_message_metadata(self):
        mem = ConversationMemory()
        msg = mem.add_message(MessageRole.TOOL, "result", session_id="s1", key="value")
        assert msg.metadata.get("key") == "value"
        assert msg.message_id is not None

    def test_message_to_dict(self):
        msg = MessageRole.USER
        mem = ConversationMemory()
        mem.add_message(msg, "Hello", session_id="s1")
        messages = mem.get_for_llm("s1")
        assert messages[0] == {"role": "user", "content": "Hello"}

    def test_session_independence(self):
        mem = ConversationMemory()
        mem.set_system_prompt("Sys A", session_id="a")
        mem.set_system_prompt("Sys B", session_id="b")
        mem.add_message(MessageRole.USER, "Q from A", session_id="a")
        mem.add_message(MessageRole.USER, "Q from B", session_id="b")
        msgs_a = mem.get_for_llm("a")
        msgs_b = mem.get_for_llm("b")
        assert msgs_a[0]["content"] == "Sys A"
        assert msgs_b[0]["content"] == "Sys B"
        assert msgs_a[1]["content"] == "Q from A"
        assert msgs_b[1]["content"] == "Q from B"


# =============================================================================
# TEST: AGENT STATE (from agent/core/state.py)
# =============================================================================

class TestAgentState:
    """Tests for AgentState and StateManager."""

    def test_agent_state_initialization(self):
        state = AgentState(session_id="test-session", user_input="check this code")
        assert state.session_id == "test-session"
        assert state.user_input == "check this code"
        assert state.current_iteration == 0
        assert state.steps == []
        assert state.observations == []
        assert state.final_answer == ""
        assert state.error is None
        assert state.created_at > 0

    def test_agent_state_add_step(self):
        state = AgentState()
        state.add_step(StateStepType.THINK, "Need to analyze")
        assert len(state.steps) == 1
        assert state.steps[0].type == StateStepType.THINK
        assert state.steps[0].content == "Need to analyze"

    def test_agent_state_add_observation(self):
        state = AgentState()
        state.current_iteration = 2
        state.add_observation("pylint", {"issues": 3})
        assert len(state.observations) == 1
        assert state.observations[0]["tool"] == "pylint"
        assert state.observations[0]["iteration"] == 2

    def test_get_observations_text(self):
        state = AgentState()
        assert "No observations yet" in state.get_observations_text()
        state.add_observation("pylint", "Found 3 issues")
        text = state.get_observations_text()
        assert "[Tool: pylint]" in text
        assert "Found 3 issues" in text

    def test_get_thinking_history(self):
        state = AgentState()
        state.add_step(StateStepType.THINK, "thought 1")
        state.add_step(StateStepType.OBSERVE, "result 1")
        state.add_step(StateStepType.THINK, "thought 2")
        history = state.get_thinking_history()
        assert len(history) == 2
        assert history[0] == "thought 1"
        assert history[1] == "thought 2"

    def test_reset_state(self):
        state = AgentState(session_id="fixed-id", user_input="original")
        state.add_step(StateStepType.THINK, "a")
        state.add_observation("tool", "result")
        state.current_iteration = 5
        state.final_answer = "done"
        state.reset()
        assert state.steps == []
        assert state.observations == []
        assert state.current_iteration == 0
        assert state.final_answer == ""
        assert state.error is None
        assert state.user_input == ""
        assert state.session_id == "fixed-id"

    def test_state_manager_create(self):
        mgr = StateManager()
        state = mgr.create_state("test input", session_id="s1")
        assert state.session_id == "s1"
        assert state.user_input == "test input"

    def test_state_manager_get(self):
        mgr = StateManager()
        mgr.create_state("input", session_id="s1")
        state = mgr.get_state("s1")
        assert state is not None
        assert state.user_input == "input"
        assert mgr.get_state("nonexistent") is None

    def test_state_manager_delete(self):
        mgr = StateManager()
        mgr.create_state("input", session_id="s1")
        assert mgr.get_state("s1") is not None
        mgr.delete_state("s1")
        assert mgr.get_state("s1") is None

    def test_state_manager_list(self):
        mgr = StateManager()
        mgr.create_state("a", session_id="s1")
        mgr.create_state("b", session_id="s2")
        sessions = mgr.list_sessions()
        assert "s1" in sessions
        assert "s2" in sessions

    def test_state_manager_reuse_resets(self):
        mgr = StateManager()
        s1 = mgr.create_state("first", session_id="s1")
        s1.add_step(StateStepType.THINK, "old step")
        s2 = mgr.create_state("second", session_id="s1")
        assert s2 is s1
        assert s2.user_input == "second"
        assert s2.steps == []


# =============================================================================
# TEST: REACT LOOP (from agent/core/react_loop.py)
# =============================================================================

class TestReACTConfig:
    """Tests for ReACTConfig."""

    def test_default_config(self):
        config = ReACTConfig()
        assert config.max_iterations == 8
        assert config.timeout_seconds == 120
        assert config.reflection_enabled is True
        assert config.min_confidence == 0.7
        assert config.verbose is False

    def test_custom_config(self):
        config = ReACTConfig(max_iterations=3, timeout_seconds=30, reflection_enabled=False)
        assert config.max_iterations == 3
        assert config.timeout_seconds == 30
        assert config.reflection_enabled is False


class TestLoopResult:
    """Tests for LoopResult."""

    def test_default_result(self):
        result = LoopResult(status=LoopStatus.SUCCESS)
        assert result.status == LoopStatus.SUCCESS
        assert result.final_answer == ""
        assert result.iterations_used == 0
        assert result.tool_calls == []
        assert result.thinking_trace == []
        assert result.error is None
        assert result.duration_seconds == 0.0

    def test_full_result(self):
        result = LoopResult(
            status=LoopStatus.MAX_ITERATIONS,
            final_answer="Best effort answer",
            iterations_used=8,
            tool_calls=[{"tool": "pylint", "input": {}}],
            thinking_trace=["thought 1"],
            error=None,
            duration_seconds=12.5,
        )
        assert result.status == LoopStatus.MAX_ITERATIONS
        assert result.final_answer == "Best effort answer"
        assert result.iterations_used == 8
        assert len(result.tool_calls) == 1
        assert result.duration_seconds == 12.5


class TestReACTLoop:
    """Tests for ReACTLoop with MockLLMClient."""

    @pytest.mark.asyncio
    async def test_loop_initialization(self):
        llm = MockLLMClient()
        memory = ConversationMemory()
        registry = ToolRegistry()
        loop = ReACTLoop(llm=llm, memory=memory, registry=registry)
        assert loop.llm is llm
        assert loop.memory is memory
        assert loop.registry is registry
        assert loop.config.max_iterations == 8

    @pytest.mark.asyncio
    async def test_loop_returns_loop_result(self):
        llm = MockLLMClient(default_response='{"type": "final_answer", "answer": "Done."}')
        memory = ConversationMemory()
        registry = make_registry()
        loop = ReACTLoop(llm=llm, memory=memory, registry=registry)
        result = await loop.run("test input")
        assert isinstance(result, LoopResult)

    @pytest.mark.asyncio
    async def test_loop_success_with_final_answer(self):
        llm = MockLLMClient(
            default_response='{"type": "final_answer", "answer": "Code review complete."}'
        )
        memory = ConversationMemory()
        registry = ToolRegistry()
        loop = ReACTLoop(llm=llm, memory=memory, registry=registry)
        result = await loop.run("Review my code")
        assert result.status == LoopStatus.SUCCESS
        assert "Code review complete" in result.final_answer

    @pytest.mark.asyncio
    async def test_loop_tool_call_and_reflection(self):
        responses = iter([
            '{"type": "tool_call", "tool": "simple_tool", "input": {"key": "value"}}',
            "TASK COMPLETE. Done.",
            "Final answer: All good.",
        ])
        class SequenceMockLLM(MockLLMClient):
            async def generate(self, prompt: str, **kwargs: Any) -> LLMResponse:
                self.call_count += 1
                try:
                    content = next(responses)
                except StopIteration:
                    content = "Done."
                return LLMResponse(success=True, text=content)

        llm = SequenceMockLLM()
        registry = make_registry()
        memory = ConversationMemory()
        loop = ReACTLoop(llm=llm, memory=memory, registry=registry)
        result = await loop.run("Run simple tool")
        assert result.status == LoopStatus.SUCCESS
        assert len(result.tool_calls) >= 1
        assert result.tool_calls[0]["tool"] == "simple_tool"

    @pytest.mark.asyncio
    async def test_loop_handles_missing_tool(self):
        llm = MockLLMClient(
            default_response='{"type": "tool_call", "tool": "nonexistent", "input": {}}'
        )
        memory = ConversationMemory()
        registry = ToolRegistry()
        loop = ReACTLoop(llm=llm, memory=memory, registry=registry)
        result = await loop.run("Use missing tool")
        # Should not crash - gracefully handles missing tool
        assert result.status in (LoopStatus.SUCCESS, LoopStatus.MAX_ITERATIONS)

    @pytest.mark.asyncio
    async def test_loop_handles_tool_crash(self):
        responses = iter([
            '{"type": "tool_call", "tool": "crashing_tool", "input": {}}',
            "TASK COMPLETE.",
            "Done with errors.",
        ])
        class CrashRecoveryLLM(MockLLMClient):
            async def generate(self, prompt: str, **kwargs: Any) -> LLMResponse:
                self.call_count += 1
                try:
                    content = next(responses)
                except StopIteration:
                    content = "Done."
                return LLMResponse(success=True, text=content)

        llm = CrashRecoveryLLM()
        memory = ConversationMemory()
        registry = make_registry()
        loop = ReACTLoop(llm=llm, memory=memory, registry=registry)
        result = await loop.run("Use crashing tool")
        assert result.status == LoopStatus.SUCCESS

    @pytest.mark.asyncio
    async def test_loop_max_iterations(self):
        never_done = MockLLMClient(
            default_response='{"type": "tool_call", "tool": "", "input": {}}'
        )
        config = ReACTConfig(max_iterations=2, reflection_enabled=False)
        memory = ConversationMemory()
        registry = ToolRegistry()
        loop = ReACTLoop(llm=never_done, memory=memory, registry=registry, config=config)
        result = await loop.run("test")
        assert result.iterations_used <= 2

    @pytest.mark.asyncio
    async def test_parse_action_json(self):
        llm = MockLLMClient()
        memory = ConversationMemory()
        registry = ToolRegistry()
        loop = ReACTLoop(llm=llm, memory=memory, registry=registry)
        action = loop._parse_action('{"type": "final_answer", "answer": "Yes."}')
        assert action["type"] == "final_answer"
        assert action["answer"] == "Yes."

    @pytest.mark.asyncio
    async def test_parse_action_tool_call(self):
        llm = MockLLMClient()
        memory = ConversationMemory()
        registry = ToolRegistry()
        loop = ReACTLoop(llm=llm, memory=memory, registry=registry)
        action = loop._parse_action(
            '{"type": "tool_call", "tool": "pylint", "input": {"file": "x.py"}}'
        )
        assert action["type"] == "tool_call"
        assert action["tool"] == "pylint"
        assert action["input"]["file"] == "x.py"

    @pytest.mark.asyncio
    async def test_should_stop_reflection_keywords(self):
        llm = MockLLMClient()
        memory = ConversationMemory()
        registry = ToolRegistry()
        loop = ReACTLoop(llm=llm, memory=memory, registry=registry)
        assert loop._should_stop_reflection("TASK COMPLETE") is True
        assert loop._should_stop_reflection("Done") is True
        assert loop._should_stop_reflection("sufficient information") is True
        assert loop._should_stop_reflection("Continue analyzing") is False

    @pytest.mark.asyncio
    async def test_loop_with_empty_registry(self):
        llm = MockLLMClient(default_response='{"type": "final_answer", "answer": "Done."}')
        memory = ConversationMemory()
        registry = ToolRegistry()
        loop = ReACTLoop(llm=llm, memory=memory, registry=registry)
        result = await loop.run("test")
        assert result.status == LoopStatus.SUCCESS


# =============================================================================
# TEST: MODERN TOOL ORCHESTRATOR (from agent/core/orchestrator.py)
# =============================================================================

class TestModernToolOrchestrator:
    """Tests for the modern ToolOrchestrator."""

    @pytest.mark.asyncio
    async def test_initialization(self):
        registry = make_registry()
        orch = ToolOrchestrator(registry)
        assert orch.registry is registry
        assert orch.max_parallel == 3

    @pytest.mark.asyncio
    async def test_call_single_success(self):
        registry = make_registry()
        orch = ToolOrchestrator(registry)
        result = await orch.call_single("simple_tool", {"key": "hello"})
        assert result.success is True
        assert result.data["value"] == "hello"

    @pytest.mark.asyncio
    async def test_call_single_failure(self):
        registry = make_registry()
        orch = ToolOrchestrator(registry)
        result = await orch.call_single("failing_tool", {})
        assert result.success is False
        assert "Intentional failure" in result.error

    @pytest.mark.asyncio
    async def test_call_single_tool_not_found(self):
        registry = make_registry()
        orch = ToolOrchestrator(registry)
        result = await orch.call_single("nonexistent", {})
        assert result.success is False
        assert "not registered" in result.error

    @pytest.mark.asyncio
    async def test_call_single_crash(self):
        registry = make_registry()
        orch = ToolOrchestrator(registry)
        result = await orch.call_single("crashing_tool", {})
        assert result.success is False
        assert "Simulated crash" in result.error

    @pytest.mark.asyncio
    async def test_call_parallel_all_success(self):
        registry = make_registry()
        orch = ToolOrchestrator(registry)
        result = await orch.call_parallel([
            ("simple_tool", {"key": "a"}),
            ("simple_tool", {"key": "b"}),
        ])
        assert result.all_succeeded is True
        assert len(result.results) >= 1  # same tool name overwrites in dict
        assert result.results["simple_tool"].data["value"] == "b"  # last write wins

    @pytest.mark.asyncio
    async def test_call_parallel_empty(self):
        registry = make_registry()
        orch = ToolOrchestrator(registry)
        result = await orch.call_parallel([])
        assert result.all_succeeded is True
        assert len(result.results) == 0

    @pytest.mark.asyncio
    async def test_call_parallel_mixed(self):
        registry = make_registry()
        orch = ToolOrchestrator(registry)
        result = await orch.call_parallel([
            ("simple_tool", {"key": "ok"}),
            ("failing_tool", {}),
        ])
        assert result.all_succeeded is False
        assert "simple_tool" in result.results
        assert "failing_tool" in result.errors

    @pytest.mark.asyncio
    async def test_call_sequential(self):
        registry = make_registry()
        orch = ToolOrchestrator(registry)
        result = await orch.call_sequential([
            ("simple_tool", {"key": "first"}),
            ("simple_tool", {"key": "second"}),
        ])
        assert result.all_succeeded is True
        assert len(result.results) >= 1  # same tool name overwrites in dict
        assert result.results["simple_tool"].data["value"] == "second"  # last wins

    @pytest.mark.asyncio
    async def test_call_sequential_with_failure(self):
        registry = make_registry()
        orch = ToolOrchestrator(registry)
        result = await orch.call_sequential([
            ("simple_tool", {"key": "ok"}),
            ("failing_tool", {}),
        ])
        assert result.all_succeeded is False
        assert "simple_tool" in result.results
        assert "failing_tool" in result.errors

    @pytest.mark.asyncio
    async def test_execution_logging(self):
        registry = make_registry()
        orch = ToolOrchestrator(registry)
        await orch.call_single("simple_tool", {})
        logs = orch.get_recent_logs()
        assert len(logs) == 1
        assert logs[0]["tool"] == "simple_tool"
        assert logs[0]["success"] is True

    @pytest.mark.asyncio
    async def test_execution_logging_limit(self):
        registry = make_registry()
        orch = ToolOrchestrator(registry)
        for i in range(150):
            await orch.call_single("simple_tool", {"key": str(i)})
        logs = orch.get_recent_logs(limit=100)
        assert len(logs) <= 100

    def test_orchestration_result_defaults(self):
        r = OrchestrationResult()
        assert r.results == {}
        assert r.errors == {}
        assert r.total_duration == 0.0
        assert r.all_succeeded is True

    def test_orchestration_result_text(self):
        r = OrchestrationResult()
        assert "No tool executions" in r.to_text()
        r.results["tool_a"] = ToolResult(success=True, data={"status": "ok"})
        text = r.to_text()
        assert "[tool_a]" in text
        r.errors["tool_b"] = "Failed"
        text2 = r.to_text()
        assert "[tool_b ERROR]" in text2

    def test_orchestration_result_failure(self):
        r = OrchestrationResult(errors={"tool": "error"})
        assert r.all_succeeded is False


# =============================================================================
# TEST: MODERN CODE REVIEW AGENT (from agent/agent.py)
# =============================================================================

class TestModernCodeReviewAgent:
    """Tests for the modern CodeReviewAgent."""

    @pytest.mark.asyncio
    async def test_initialization_defaults(self):
        llm = MockLLMClient()
        agent = CodeReviewAgent(llm=llm, auto_load_tools=False)
        assert agent.llm is llm
        assert len(agent.tool_registry) == 0
        assert agent.memory is not None
        assert agent.state_manager is not None
        assert agent.orchestrator is not None
        assert agent.react_loop is not None

    @pytest.mark.asyncio
    async def test_register_tool(self):
        llm = MockLLMClient()
        agent = CodeReviewAgent(llm=llm, auto_load_tools=False)
        agent.register_tool(SimpleTool())
        assert agent.tool_registry.get("simple_tool") is not None
        assert len(agent.tool_registry) == 1

    @pytest.mark.asyncio
    async def test_register_tools_bulk(self):
        llm = MockLLMClient()
        agent = CodeReviewAgent(llm=llm, auto_load_tools=False)
        agent.register_tools([SimpleTool(), FailingTool()])
        assert len(agent.tool_registry) == 2

    @pytest.mark.asyncio
    async def test_review_returns_loop_result(self):
        llm = MockLLMClient(
            default_response='{"type": "final_answer", "answer": "Review complete."}'
        )
        agent = CodeReviewAgent(llm=llm, auto_load_tools=False)
        result = await agent.review("Check my code")
        assert isinstance(result, LoopResult)
        assert result.status == LoopStatus.SUCCESS

    @pytest.mark.asyncio
    async def test_review_with_session_id(self):
        llm = MockLLMClient(
            default_response='{"type": "final_answer", "answer": "Done."}'
        )
        agent = CodeReviewAgent(llm=llm, auto_load_tools=False)
        result = await agent.review("test", session_id="my-session")
        assert result.final_answer is not None
        state = agent.get_session_state("my-session")
        assert state is not None
        assert state.final_answer == result.final_answer

    @pytest.mark.asyncio
    async def test_review_with_context(self):
        llm = MockLLMClient(
            default_response='{"type": "final_answer", "answer": "Done."}'
        )
        agent = CodeReviewAgent(llm=llm, auto_load_tools=False)
        result = await agent.review("test", context={"file": "main.py", "language": "python"})
        assert result.status == LoopStatus.SUCCESS

    @pytest.mark.asyncio
    async def test_chat_returns_loop_result(self):
        llm = MockLLMClient(default_response="Hello! I can review your code.")
        agent = CodeReviewAgent(llm=llm, auto_load_tools=False)
        result = await agent.chat("Hi")
        assert isinstance(result, LoopResult)
        assert result.status == LoopStatus.SUCCESS
        assert "Hello" in result.final_answer

    @pytest.mark.asyncio
    async def test_get_session_history(self):
        llm = MockLLMClient(
            default_response='{"type": "final_answer", "answer": "Done."}'
        )
        agent = CodeReviewAgent(llm=llm, auto_load_tools=False)
        await agent.review("test", session_id="hist-session")
        history = agent.get_session_history("hist-session")
        assert len(history) > 0
        assert any(m["role"] == "user" for m in history)

    @pytest.mark.asyncio
    async def test_get_stats(self):
        llm = MockLLMClient()
        agent = CodeReviewAgent(llm=llm, auto_load_tools=False)
        agent.register_tool(SimpleTool())
        stats = agent.get_stats()
        assert "active_sessions" in stats
        assert "session_count" in stats
        assert "total_messages" in stats
        assert "registered_tools" in stats
        assert "tool_count" in stats
        assert stats["tool_count"] == 1

    @pytest.mark.asyncio
    async def test_clear_session(self):
        llm = MockLLMClient(
            default_response='{"type": "final_answer", "answer": "Done."}'
        )
        agent = CodeReviewAgent(llm=llm, auto_load_tools=False)
        await agent.review("test", session_id="clear-me")
        assert agent.get_session_state("clear-me") is not None
        agent.clear_session("clear-me")
        assert agent.get_session_state("clear-me") is None

    @pytest.mark.asyncio
    async def test_auto_load_tools_enabled(self):
        llm = MockLLMClient()
        agent = CodeReviewAgent(llm=llm, auto_load_tools=True, skip_team_project=True)
        # With skip_team_project=True and no built-in tools package,
        # registry should be empty or only have team project tools if available
        assert isinstance(agent.tool_registry, ToolRegistry)

    @pytest.mark.asyncio
    async def test_multiple_reviews_independent(self):
        llm = MockLLMClient(
            default_response='{"type": "final_answer", "answer": "Answer."}'
        )
        agent = CodeReviewAgent(llm=llm, auto_load_tools=False)
        r1 = await agent.review("Request A", session_id="s-a")
        r2 = await agent.review("Request B", session_id="s-b")
        assert r1.status == LoopStatus.SUCCESS
        assert r2.status == LoopStatus.SUCCESS
        state_a = agent.get_session_state("s-a")
        state_b = agent.get_session_state("s-b")
        assert state_a.user_input == "Request A"
        assert state_b.user_input == "Request B"
