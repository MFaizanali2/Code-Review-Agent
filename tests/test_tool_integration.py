"""
Comprehensive tool integration tests.

Covers:
- Tool discovery (dynamic scanning)
- Tool validation (interface contract)
- Tool registration (registry add/lookup)
- Agent tool loading (auto-load on init)
- Missing tool handling (graceful errors)
- Adapter bridge (Team Project legacy tools)
"""

from __future__ import annotations

import pytest

from agent.tools.base import BaseTool, ToolResult, ToolSchema
from agent.tools.loader import (
    discover_tools,
    instantiate_tools,
    load_builtin_tools,
    validate_tool,
    validate_all_tools,
)
from agent.tools.registry import ToolRegistry
from agent.tools.team_project_bridge import TeamProjectToolAdapter


# =============================================================================
# HELPER TOOLS FOR TESTING
# =============================================================================

class WorkingTool(BaseTool):
    """A proper tool that follows the BaseTool contract."""

    @property
    def name(self) -> str:
        return "test_tool"

    @property
    def description(self) -> str:
        return "A test tool for unit tests"

    async def run(self, tool_input: dict) -> ToolResult:
        return ToolResult(success=True, data={"processed": tool_input.get("value", "none")})


class BrokenTool:
    """A class that does NOT inherit from BaseTool."""

    @property
    def name(self) -> str:
        return "broken_tool"

    async def run(self, tool_input: dict) -> dict:
        return {"status": "ok"}


class MissingRunTool(BaseTool):
    """A BaseTool subclass with a non-async run (invalid contract)."""

    @property
    def name(self) -> str:
        return "missing_run"

    @property
    def description(self) -> str:
        return "Missing run method"

    def run(self, tool_input: dict) -> ToolResult:
        return ToolResult(success=True, data={})


class EmptyNameTool(BaseTool):
    """A tool with an empty name."""

    @property
    def name(self) -> str:
        return ""

    @property
    def description(self) -> str:
        return "Empty name tool"

    async def run(self, tool_input: dict) -> ToolResult:
        return ToolResult(success=True, data={})


# =============================================================================
# PART 1: TOOL DISCOVERY TESTS
# =============================================================================

class TestToolDiscovery:
    """Test dynamic tool discovery from packages."""

    def test_discover_returns_list(self):
        """discover_tools() should return a list."""
        tools = discover_tools([])
        assert isinstance(tools, list)

    def test_discover_handles_missing_package(self):
        """discover_tools() should not crash if package missing."""
        tools = discover_tools(["nonexistent.package"])
        assert isinstance(tools, list)
        assert len(tools) == 0

    def test_discover_handles_empty_list(self):
        """discover_tools() should handle empty package list."""
        tools = discover_tools([])
        assert isinstance(tools, list)

    def test_instantiate_tools_empty(self):
        """instantiate_tools() should handle empty list."""
        tools = instantiate_tools([])
        assert isinstance(tools, list)
        assert len(tools) == 0

    def test_instantiate_tools_skips_failures(self):
        """instantiate_tools() should skip classes that fail to init."""
        class FailingTool(BaseTool):
            @property
            def name(self) -> str:
                return "failing"
            @property
            def description(self) -> str:
                return "failing"
            async def run(self, tool_input: dict) -> ToolResult:
                raise RuntimeError("never gets here")
            def __init__(self):
                raise ValueError("Cannot instantiate")

        tools = instantiate_tools([WorkingTool, FailingTool])
        assert len(tools) == 1
        assert isinstance(tools[0], WorkingTool)


# =============================================================================
# PART 2: TOOL VALIDATION TESTS
# =============================================================================

class TestToolValidation:
    """Test tool validation logic."""

    def test_validate_working_tool(self):
        """A proper tool should pass validation."""
        is_valid, error = validate_tool(WorkingTool())
        assert is_valid is True
        assert error is None

    def test_validate_broken_tool(self):
        """A non-BaseTool should fail validation."""
        is_valid, error = validate_tool(BrokenTool())
        assert is_valid is False
        assert error is not None
        assert "must be a BaseTool" in error

    def test_validate_missing_run(self):
        """A BaseTool without run() should fail."""
        is_valid, error = validate_tool(MissingRunTool())
        assert is_valid is False
        assert "run()" in error

    def test_validate_empty_name(self):
        """A tool with empty name should fail."""
        is_valid, error = validate_tool(EmptyNameTool())
        assert is_valid is False
        assert "empty" in error

    def test_validate_none(self):
        """validate_tool(None) should fail."""
        is_valid, error = validate_tool(None)
        assert is_valid is False


# =============================================================================
# PART 3: TOOL REGISTRY TESTS
# =============================================================================

class TestToolRegistryIntegration:
    """Test ToolRegistry with validation and loading."""

    def test_registry_register_validated(self):
        """Registry should accept valid tools."""
        registry = ToolRegistry()
        tool = WorkingTool()
        registry.register(tool)
        assert "test_tool" in registry

    def test_registry_validate_all(self):
        """validate_all() should check all tools."""
        registry = ToolRegistry()
        registry.register(WorkingTool())
        results = registry.validate_all()
        assert "test_tool" in results
        assert results["test_tool"] is None

    def test_registry_validate_all_mixed(self):
        """validate_all() should report invalid tools."""
        registry = ToolRegistry()
        registry._tools["bad"] = BrokenTool()
        results = registry.validate_all()
        assert "bad" in results
        assert results["bad"] is not None

    def test_registry_get_safe_found(self):
        """get_safe() should return tool if registered."""
        registry = ToolRegistry()
        registry.register(WorkingTool())
        tool = registry.get_safe("test_tool")
        assert tool is not None
        assert isinstance(tool, WorkingTool)

    def test_registry_get_safe_missing(self):
        """get_safe() should return None for missing tool."""
        registry = ToolRegistry()
        tool = registry.get_safe("nonexistent")
        assert tool is None

    def test_validate_all_tools_empty(self):
        """validate_all_tools() on empty registry."""
        registry = ToolRegistry()
        results = validate_all_tools(registry)
        assert results == {}


# =============================================================================
# PART 4: BUILT-IN TOOL LOADING
# =============================================================================

class TestBuiltinToolLoading:
    """Test loading built-in tools."""

    def test_load_builtin_tools_returns_registry(self):
        """load_builtin_tools() should return a ToolRegistry."""
        registry = load_builtin_tools(skip_team_project=True)
        assert isinstance(registry, ToolRegistry)

    def test_load_builtin_tools_skip_team_project(self):
        """With skip_team_project, built-in tools should still load."""
        registry = load_builtin_tools(skip_team_project=True)
        assert len(registry) == 5

    def test_load_builtin_tools_without_skip(self):
        """Without skip, all built-in tools should load."""
        registry = load_builtin_tools(skip_team_project=False)
        assert len(registry) == 5

    def test_load_builtin_tools_into_existing(self):
        """load_builtin_tools() should populate existing registry."""
        registry = ToolRegistry()
        result = load_builtin_tools(registry, skip_team_project=True)
        assert result is registry

    def test_load_builtin_tools_does_not_duplicate(self):
        """Loading same tools twice should not duplicate."""
        registry = load_builtin_tools(skip_team_project=True)
        count1 = len(registry)
        load_builtin_tools(registry, skip_team_project=True)
        count2 = len(registry)
        # Tools with same name overwrite, so count stays same
        assert count1 == count2 and count1 == 5


# =============================================================================
# PART 5: ADAPTER BRIDGE
# =============================================================================

class TestAdapterBridge:
    """Test the TeamProjectToolAdapter for legacy tools."""

    async def test_adapter_wraps_working_tool(self):
        """TeamProjectToolAdapter should wrap any tool with execute()."""
        class SimpleTool:
            def __init__(self):
                self.name = "simple"
                self.description = "A simple tool"

            async def execute(self, value: str = "default") -> dict:
                return {"status": "success", "data": f"processed {value}"}

        adapter = TeamProjectToolAdapter(SimpleTool())
        assert adapter.name == "simple"
        assert adapter.description == "A simple tool"
        is_valid, error = validate_tool(adapter)
        assert is_valid is True, error

    async def test_adapter_run_success(self):
        """Adapter.run() should delegate to execute()."""
        class SuccessTool:
            def __init__(self):
                self.name = "success"
                self.description = "Always succeeds"
            async def execute(self, **kwargs) -> dict:
                return {"status": "success", "result": "ok"}

        adapter = TeamProjectToolAdapter(SuccessTool())
        result = await adapter.run({})
        assert result.success is True
        assert result.data["result"] == "ok"

    async def test_adapter_run_error_status(self):
        """Adapter.run() should handle dict with status=error."""
        class FailingTool:
            def __init__(self):
                self.name = "fail"
                self.description = "Always fails"
            async def execute(self, **kwargs) -> dict:
                return {"status": "error", "message": "Something broke"}

        adapter = TeamProjectToolAdapter(FailingTool())
        result = await adapter.run({})
        assert result.success is False
        assert "Something broke" in result.error

    async def test_adapter_run_exception(self):
        """Adapter.run() should catch exceptions from execute()."""
        class CrashingTool:
            def __init__(self):
                self.name = "crash"
                self.description = "Always crashes"
            async def execute(self, **kwargs) -> dict:
                raise RuntimeError("Unexpected crash")

        adapter = TeamProjectToolAdapter(CrashingTool())
        result = await adapter.run({})
        assert result.success is False
        assert "Unexpected crash" in result.error

    def test_adapter_schema_provides_name(self):
        """Adapter.schema() should use wrapped tool's name."""
        class NamedTool:
            def __init__(self):
                self.name = "named_tool"
                self.description = "Has a name"

        adapter = TeamProjectToolAdapter(NamedTool())
        schema = adapter.schema()
        assert schema.name == "named_tool"
        assert schema.description == "Has a name"

    async def test_validate_team_project_adapter(self):
        """TeamProjectToolAdapter should pass validation."""
        class ValidTool:
            def __init__(self):
                self.name = "valid_tp"
                self.description = "A valid Team Project tool"
            async def execute(self, **kwargs) -> dict:
                return {"status": "success"}

        adapter = TeamProjectToolAdapter(ValidTool())
        is_valid, error = validate_tool(adapter)
        assert is_valid is True, error


# =============================================================================
# PART 6: AGENT TOOL INTEGRATION
# =============================================================================

class TestAgentToolIntegration:
    """Test tools work end-to-end through the agent."""

    async def test_registry_validate_with_agent_tools(self):
        """Tools registered in agent should pass validation."""
        from agent.agent import CodeReviewAgent
        from agent.llm.client import MockLLMClient

        llm = MockLLMClient()
        agent = CodeReviewAgent(llm=llm, auto_load_tools=False)

        tool = WorkingTool()
        agent.register_tool(tool)

        results = agent.tool_registry.validate_all()
        assert "test_tool" in results
        assert results["test_tool"] is None

    async def test_agent_with_no_tools(self):
        """Agent should work with empty registry."""
        from agent.agent import CodeReviewAgent
        from agent.llm.client import MockLLMClient

        llm = MockLLMClient()
        agent = CodeReviewAgent(llm=llm, auto_load_tools=False)

        assert len(agent.tool_registry) == 0
        assert agent.tool_registry.list_names() == []

    async def test_agent_auto_loads_tools_by_default(self):
        """Agent should auto-load tools unless disabled."""
        from agent.agent import CodeReviewAgent
        from agent.llm.client import MockLLMClient

        llm = MockLLMClient()
        agent = CodeReviewAgent(llm=llm)

        # Should auto-load built-in tools
        # At minimum, validate_all should not crash
        results = agent.tool_registry.validate_all()
        assert isinstance(results, dict)

    async def test_agent_orchestrator_uses_registry(self):
        """Agent's orchestrator should use the shared registry."""
        from agent.agent import CodeReviewAgent
        from agent.llm.client import MockLLMClient

        llm = MockLLMClient()
        agent = CodeReviewAgent(llm=llm, auto_load_tools=False)

        tool = WorkingTool()
        agent.register_tool(tool)

        result = await agent.orchestrator.call_single(
            "test_tool", {"value": "hello"}
        )
        assert result.success is True
        assert result.data["processed"] == "hello"

    async def test_missing_tool_graceful_error(self):
        """Orchestrator should handle missing tools gracefully."""
        from agent.core.orchestrator import ToolOrchestrator

        registry = ToolRegistry()
        orchestrator = ToolOrchestrator(registry)

        result = await orchestrator.call_single("nonexistent", {})
        assert result.success is False
        assert "not registered" in result.error

    async def test_assess_builtin_tools(self):
        """Test loading built-in tools into agent."""
        from agent.agent import CodeReviewAgent
        from agent.llm.client import MockLLMClient

        llm = MockLLMClient()
        agent = CodeReviewAgent(llm=llm, auto_load_tools=False)

        try:
            from agent.tools.builtin.github_tool import GitHubTool
            from agent.tools.builtin.code_analyzer import CodeAnalyzerTool
            from agent.tools.builtin.security_checker import SecurityCheckerTool
            from agent.tools.builtin.performance_checker import PerformanceCheckerTool
            from agent.tools.builtin.report_generator import ReportGeneratorTool

            agent.register_tools([
                GitHubTool(),
                CodeAnalyzerTool(),
                SecurityCheckerTool(),
                PerformanceCheckerTool(),
                ReportGeneratorTool(),
            ])

            results = agent.tool_registry.validate_all()
            invalid = [n for n, e in results.items() if e is not None]
            assert len(invalid) == 0, f"Invalid tools: {invalid}"
        except ImportError:
            pytest.skip("Built-in tools not available")


# =============================================================================
# PART 7: TOOL DISCOVERY END-TO-END
# =============================================================================

class TestEndToEndToolFlow:
    """Full tool lifecycle: discovery -> validate -> register -> execute."""

    async def test_full_flow(self):
        """Test the complete tool lifecycle."""
        # 1. Instantiate a tool
        tool = WorkingTool()

        # 2. Validate
        is_valid, error = validate_tool(tool)
        assert is_valid is True

        # 3. Register
        registry = ToolRegistry()
        registry.register(tool)
        assert "test_tool" in registry

        # 4. Lookup
        found = registry.get("test_tool")
        assert found is tool

        # 5. Execute
        result = await found.run({"value": "world"})
        assert result.success is True
        assert result.data["processed"] == "world"

    async def test_missing_tool_handling(self):
        """Test graceful handling of missing tools."""
        from agent.core.orchestrator import ToolOrchestrator

        registry = ToolRegistry()
        orchestrator = ToolOrchestrator(registry)

        result = await orchestrator.call_single("ghost_tool", {})
        assert result.success is False
        assert "not registered" in result.error

    def test_validate_all_returns_all(self):
        """validate_all should check every registered tool."""
        registry = ToolRegistry()
        registry.register(WorkingTool())
        registry._tools["invalid"] = BrokenTool()
        results = validate_all_tools(registry)
        assert len(results) == 2
        assert results["test_tool"] is None
        # BrokenTool has .name = "broken_tool", not "invalid"
        assert results["broken_tool"] is not None
