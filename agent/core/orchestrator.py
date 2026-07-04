"""
Tool Orchestrator - multiple tools ko coordinate karo.
Yeh layer LLM ke tool calls ko receive karke sahi tool ko invoke karti hai,
parallel execution handle karti hai, aur results aggregate karti hai.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any

from agent.tools.base import ToolResult
from agent.tools.registry import ToolRegistry

logger = logging.getLogger(__name__)


@dataclass
class OrchestrationResult:
    """Multiple tool calls ke aggregated results."""
    results: dict[str, ToolResult] = field(default_factory=dict)
    errors: dict[str, str] = field(default_factory=dict)
    total_duration: float = 0.0

    @property
    def all_succeeded(self) -> bool:
        """Check karo sab tools successfully execute hue ya nahi."""
        return len(self.errors) == 0

    def to_text(self) -> str:
        """Sab results ko readable text mein convert karo - LLM ke liye."""
        lines = []
        for name, result in self.results.items():
            lines.append(f"[{name}] {result.to_observation()}")
        for name, err in self.errors.items():
            lines.append(f"[{name} ERROR] {err}")
        return "\n".join(lines) if lines else "No tool executions."


class ToolOrchestrator:
    """
    Tools ko smartly manage karne ka central class.
    Single tool call, parallel multi-tool call, aur dependencies handle karta hai.

    Abhi simple version hai - future mein retry, caching, rate limiting add hogi.
    """

    def __init__(self, registry: ToolRegistry, max_parallel: int = 3) -> None:
        self.registry = registry
        self.max_parallel = max_parallel
        self._execution_log: list[dict[str, Any]] = []
        logger.info("ToolOrchestrator initialized with max_parallel=%d", max_parallel)

    async def call_single(self, tool_name: str, tool_input: dict[str, Any]) -> ToolResult:
        """
        Ek single tool call karo.
        Errors ko gracefully handle karo - exception propagate nahi karta.
        """
        tool = self.registry.get(tool_name)
        if tool is None:
            msg = f"Tool '{tool_name}' not registered"
            logger.error(msg)
            return ToolResult(success=False, data=None, error=msg)

        logger.info("Orchestrating single tool call: %s", tool_name)
        try:
            result = await tool.run(tool_input)
            self._log_execution(tool_name, tool_input, result, success=result.success)
            return result
        except Exception as exc:  # noqa: BLE001
            logger.exception("Tool %s crashed: %s", tool_name, exc)
            self._log_execution(tool_name, tool_input, None, success=False, error=str(exc))
            return ToolResult(success=False, data=None, error=str(exc))

    async def call_parallel(
        self, calls: list[tuple[str, dict[str, Any]]]
    ) -> OrchestrationResult:
        """
        Multiple tools ko parallel mein run karo.
        max_parallel se zyada concurrent calls nahi hongi (rate limit protection).

        calls format: [(tool_name, tool_input), ...]
        """
        import time as _time
        start = _time.time()
        result = OrchestrationResult()

        if not calls:
            return result

        semaphore = asyncio.Semaphore(self.max_parallel)

        async def _run_one(
            tool_name: str, tool_input: dict[str, Any]
        ) -> tuple[str, ToolResult | None, str | None]:
            async with semaphore:
                res = await self.call_single(tool_name, tool_input)
                if res.success:
                    return tool_name, res, None
                return tool_name, None, res.error or "Unknown error"

        tasks = [_run_one(name, inp) for name, inp in calls]
        outcomes = await asyncio.gather(*tasks, return_exceptions=True)

        for outcome in outcomes:
            if isinstance(outcome, Exception):
                logger.error("Parallel task raised: %s", outcome)
                continue
            name, res, err = outcome
            if res is not None:
                result.results[name] = res
            if err is not None:
                result.errors[name] = err

        result.total_duration = _time.time() - start
        logger.info(
            "Parallel execution done: %d succeeded, %d failed in %.2fs",
            len(result.results), len(result.errors), result.total_duration,
        )
        return result

    async def call_sequential(
        self, calls: list[tuple[str, dict[str, Any]]]
    ) -> OrchestrationResult:
        """
        Tools ko ek ek karke run karo - jab results depend karte hon.
        Slow hai par predictable hai.
        """
        import time as _time
        start = _time.time()
        result = OrchestrationResult()

        for tool_name, tool_input in calls:
            res = await self.call_single(tool_name, tool_input)
            if res.success:
                result.results[tool_name] = res
            else:
                result.errors[tool_name] = res.error or "Unknown error"
                # Sequential mein pehla error pe stop kar sakte hain
                # Yahan abhi continue kar rahe hain sab try karne ke liye

        result.total_duration = _time.time() - start
        return result

    def _log_execution(
        self,
        tool_name: str,
        tool_input: dict[str, Any],
        result: ToolResult | None,
        success: bool,
        error: str | None = None,
    ) -> None:
        """Execution log maintain karo - debugging aur analytics ke liye."""
        self._execution_log.append({
            "tool": tool_name,
            "input": tool_input,
            "success": success,
            "error": error,
        })
        # Memory leak se bachne ke liye last 100 entries rakhte hain
        if len(self._execution_log) > 100:
            self._execution_log = self._execution_log[-100:]

    def get_recent_logs(self, limit: int = 20) -> list[dict[str, Any]]:
        """Recent tool executions ka log dekho - debugging ke liye."""
        return self._execution_log[-limit:]
