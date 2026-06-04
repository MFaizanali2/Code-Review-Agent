"""Verification tests for updated ToolOrchestrator."""
import asyncio
from agent.agent_types import ToolResult
from agent.agent_orchestrator import ToolOrchestrator


class SuccessTool:
    name = "success_tool"

    async def run(self, params):
        await asyncio.sleep(0.01)
        return ToolResult(
            tool_name="success_tool", success=True, data={"count": params.get("n", 1)}
        )


class FailTool:
    name = "fail_tool"

    async def run(self, params):
        await asyncio.sleep(0.01)
        raise ValueError("Simulated failure")


class SlowTool:
    name = "slow_tool"

    async def run(self, params):
        await asyncio.sleep(2.0)
        return {"result": "slow"}


class DictTool:
    name = "dict_tool"

    async def run(self, params):
        return {"issues": 5, "score": 8.5}


class FlakeyTool:
    async def run(self, params):
        return {"ok": True}


async def main():
    orch = ToolOrchestrator(
        {
            "success_tool": SuccessTool(),
            "fail_tool": FailTool(),
            "slow_tool": SlowTool(),
            "dict_tool": DictTool(),
        }
    )
    print("Initial:", orch)

    # ===== CORE EXECUTION =====
    print("\n=== T1: Success ===")
    r = await orch.execute_tool("success_tool", {"n": 42}, timeout=5, retries=0)
    print(f"data={r.data}, time={r.execution_time:.3f}s")
    assert r.success and r.data["count"] == 42

    print("\n=== T2: Dict auto-wrap ===")
    r = await orch.execute_tool("dict_tool", {}, timeout=5, retries=0)
    assert r.success and r.data["issues"] == 5
    print(f"data={r.data}")

    print("\n=== T3: Tool not found ===")
    r = await orch.execute_tool("nonexistent", {}, timeout=5, retries=0)
    assert not r.success and "not found" in r.error
    print(f"error={r.error[:60]}")

    print("\n=== T4: Retry on failure (1s delay) ===")
    start = asyncio.get_event_loop().time()
    r = await orch.execute_tool("fail_tool", {}, timeout=5, retries=2)
    elapsed = asyncio.get_event_loop().time() - start
    print(f"total time={elapsed:.2f}s, error={r.error[:60]}")
    assert not r.success
    assert "3 attempts" in r.error
    # 2 retries * 1s delay = ~2s minimum
    assert elapsed >= 1.8, f"Expected ~2s with retries, got {elapsed:.2f}s"

    print("\n=== T5: Failure count tracking ===")
    print(f"failed: {orch.get_failed_tools()}")
    assert orch.get_failed_tools()["fail_tool"] == 3

    print("\n=== T6: should_retry_tool ===")
    assert not orch.should_retry_tool("fail_tool")
    assert orch.should_retry_tool("success_tool")
    print("Logic correct")

    print("\n=== T7: Failure reset on success ===")
    orch._tools["fail_tool"] = FlakeyTool()
    r = await orch.execute_tool("fail_tool", {}, timeout=5, retries=0)
    assert orch.get_failed_tools().get("fail_tool", 0) == 0
    print(f"After success, count=0")

    # ===== NEW: reset_tool_failures =====
    print("\n=== T8: reset_tool_failures() ===")
    # Force a failure
    orch._tools["fail_tool"] = FailTool()
    await orch.execute_tool("fail_tool", {}, timeout=5, retries=0)
    print(f"Before reset: {orch.get_failed_tools()}")
    assert orch.get_failed_tools()["fail_tool"] >= 1
    orch.reset_tool_failures("fail_tool")
    print(f"After reset: {orch.get_failed_tools()}")
    assert orch.get_failed_tools()["fail_tool"] == 0

    # ===== PARALLEL =====
    print("\n=== T9: Parallel execution ===")
    results = await orch.execute_tools_parallel(
        [
            ("success_tool", {"n": 1}),
            ("success_tool", {"n": 2}),
            ("dict_tool", {}),
        ]
    )
    assert len(results) == 3
    assert results[0].data["count"] == 1
    assert results[1].data["count"] == 2
    print(f"Got {len(results)} results, order preserved")

    print("\n=== T10: Parallel with missing tool ===")
    results = await orch.execute_tools_parallel(
        [
            ("success_tool", {"n": 99}),
            ("nonexistent", {}),
        ]
    )
    assert results[0].success
    assert not results[1].success
    print("Mixed results handled gracefully")

    # ===== TIMEOUT =====
    print("\n=== T11: Timeout ===")
    r = await orch.execute_tool("slow_tool", {}, timeout=1, retries=0)
    assert not r.success and "Timeout" in r.error
    print(f"timeout: {r.error[:60]}")

    # ===== NEW STATS FORMAT =====
    print("\n=== T12: New get_tool_stats() format ===")
    stats = orch.get_tool_stats()
    print(f"Total: {stats['total_executions']}")
    print(f"Successful: {stats['successful']}")
    print(f"Failed: {stats['failed']}")
    print(f"Average time: {stats['average_time']:.3f}s")
    print(f"Tools: {list(stats['tools'].keys())}")
    for tool_name, t in stats["tools"].items():
        print(f"  {tool_name}: {t}")

    # Verify new format keys
    assert "total_executions" in stats
    assert "successful" in stats
    assert "failed" in stats
    assert "average_time" in stats
    assert "tools" in stats
    # Per-tool keys
    for tool_stats in stats["tools"].values():
        assert "executions" in tool_stats
        assert "success" in tool_stats  # singular per spec
        assert "avg_time" in tool_stats  # not average_time per spec
    print("Stats format matches spec!")

    # ===== NEW: reset_history =====
    print("\n=== T13: reset_history() ===")
    pre_executions = len(orch.get_execution_history())
    pre_failed = len(orch.get_failed_tools())
    pre_tools = len(orch.get_tool_stats()["tools"])
    print(f"Before reset: executions={pre_executions}, failed_tools={pre_failed}, tracked_tools={pre_tools}")

    orch.reset_history()

    post_stats = orch.get_tool_stats()
    print(f"After reset: {post_stats}")
    assert post_stats["total_executions"] == 0
    assert post_stats["successful"] == 0
    assert post_stats["failed"] == 0
    assert post_stats["tools"] == {}
    assert orch.get_failed_tools() == {}
    assert orch.get_execution_history() == []
    print("All state cleared!")

    # Tools registry should be intact
    assert orch.tool_count == 4, f"Tool count should be preserved, got {orch.tool_count}"
    print(f"Tools registry intact: {orch.tool_count} tools")

    # ===== HELPER METHODS =====
    print("\n=== T14: _is_tool_available() ===")
    assert orch._is_tool_available("success_tool") is True
    assert orch._is_tool_available("nonexistent") is False
    print("Availability check works")

    print("\n=== T15: _get_tool() ===")
    tool = orch._get_tool("success_tool")
    assert tool is not None
    assert tool.name == "success_tool"
    missing = orch._get_tool("nonexistent")
    assert missing is None
    print("Get tool returns instance or None")

    # ===== EDGE CASES =====
    print("\n=== T16: Empty parallel ===")
    results = await orch.execute_tools_parallel([])
    assert results == []
    print("Empty list returns empty list")

    print("\n=== T17: Empty registry ===")
    empty_orch = ToolOrchestrator({})
    assert empty_orch.tool_count == 0
    stats = empty_orch.get_tool_stats()
    assert stats["total_executions"] == 0
    print("Empty registry handled")

    print("\n=== T18: Reset unknown tool failures ===")
    orch.reset_tool_failures("never_used_tool")  # no-op, no error
    print("No error on unknown tool")

    print("\n=== T19: Repr ===")
    print(f"Repr: {orch}")
    assert "tools=" in repr(orch)
    assert "executions=" in repr(orch)

    print("\n" + "=" * 50)
    print("All 19 tests passed!")
    print("=" * 50)


asyncio.run(main())
