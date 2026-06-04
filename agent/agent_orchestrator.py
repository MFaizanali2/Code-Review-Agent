"""
agent_orchestrator.py - Tool execution aur management ka central layer.
ToolOrchestrator tools ko invoke karta hai, parallel execution handle karta hai,
retry logic, timeouts, aur detailed statistics provide karta hai.

Yeh class agent aur tools ke beech ka bridge hai. ReACT loop iske through
tools ko call karta hai, isse hi results collect karta hai.

Key features:
- Async tool execution with asyncio.wait_for timeout
- Automatic retry with 1s delay between attempts
- Parallel execution via asyncio.gather
- Per-tool statistics tracking (computed on-demand)
- Thread-safe state management via RLock
- Failed tool tracking for retry decisions
- Clean reset APIs for new requests
"""

# =============================================================================
# IMPORTS
# =============================================================================
import asyncio
import logging
import threading
import time
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from agent.agent_types import ToolCall, ToolResult
from agent.constants import RETRY_ATTEMPTS, TOOL_TIMEOUT

logger = logging.getLogger(__name__)


# =============================================================================
# TOOL ORCHESTRATOR CLASS
# =============================================================================
class ToolOrchestrator:
    """
    Tools ko execute karne ka central manager.
    ReACT loop iske through tools invoke karta hai.

    Yeh class:
    - Tools ko async execute karti hai with timeout
    - Failures pe automatic retry karti hai (1s delay between attempts)
    - Multiple tools parallel chala sakti hai via asyncio.gather
    - Har tool ke statistics track karti hai
    - Thread-safe hai concurrent use ke liye
    - New request ke liye clean reset provide karti hai

    Tool interface expected:
        Tool ek object hona chahiye jiska async `run(params: dict)` method ho
        (jaise humara BaseTool). Plain async functions bhi chal sakte hain.

    Attributes:
        tool_count: Number of tools in registry (property)

    Example:
        >>> orchestrator = ToolOrchestrator({"pylint": pylint_tool})
        >>> result = await orchestrator.execute_tool("pylint", {"file": "main.py"})
        >>> print(orchestrator.get_tool_stats())
    """

    # Retry delay between attempts (seconds) - user spec: simple 1s wait
    RETRY_DELAY_SECONDS: int = 1

    def __init__(self, tools_registry: Dict[str, Any]) -> None:
        """
        ToolOrchestrator initialize karo with tools registry.

        Args:
            tools_registry: Dict mapping tool names to tool instances.
                           Values BaseTool objects ya async callables ho sakte hain.
                           Empty dict bhi valid hai (no tools case).

        Example:
            >>> orch = ToolOrchestrator({"pylint": pylint_tool, "bandit": bandit_tool})
            >>> empty_orch = ToolOrchestrator({})  # valid, no tools
        """
        # Tools registry - name to tool mapping
        self._tools: Dict[str, Any] = dict(tools_registry)

        # Execution history - chronological list of all results
        self._execution_history: List[ToolResult] = []

        # Failed tools counter - tool_name -> consecutive failure count
        # Reset hota hai success pe zero pe
        self._failed_tools: Dict[str, int] = {}

        # Per-tool statistics - tool_name -> {executions, success, total_time}
        # avg_time is computed on-demand in get_tool_stats
        self._per_tool_stats: Dict[str, Dict[str, Any]] = {}

        # Lifecycle tracking
        self._created_at: datetime = datetime.now()

        # Thread safety - RLock for reentrant calls from same thread
        self._lock = threading.RLock()

        if self._tools:
            logger.info(
                "ToolOrchestrator initialized with %d tools: %s",
                len(self._tools), list(self._tools.keys()),
            )
        else:
            logger.warning("ToolOrchestrator initialized with EMPTY registry")

    # =========================================================================
    # PROPERTIES
    # =========================================================================
    @property
    def tool_count(self) -> int:
        """Number of tools currently registered."""
        return len(self._tools)

    @property
    def registered_tools(self) -> List[str]:
        """List of registered tool names (copy)."""
        with self._lock:
            return list(self._tools.keys())

    # =========================================================================
    # CORE EXECUTION METHODS
    # =========================================================================
    async def execute_tool(
        self,
        tool_name: str,
        params: Dict[str, Any],
        timeout: int = TOOL_TIMEOUT,
        retries: int = RETRY_ATTEMPTS,
    ) -> ToolResult:
        """
        Ek single tool execute karo with timeout aur retry support.

        Flow:
        1. Tool registry mein check karo (via _is_tool_available)
        2. Try execution with asyncio.wait_for timeout
        3. Agar fail ho jaye, 1s wait karke retry
        4. Saari attempts fail hone pe final error result return karo
        5. Har attempt track hota hai (success ya failure)

        Args:
            tool_name: Registry key - konsa tool call karna hai.
            params: Tool ko pass karne wale arguments (dict).
            timeout: Har attempt ka max time in seconds (default TOOL_TIMEOUT=120).
            retries: Extra attempts after initial failure (default RETRY_ATTEMPTS=2).
                     Total attempts = 1 + retries = 3 by default.

        Returns:
            ToolResult with tool_name, success, data, error, execution_time.
            Kabhi bhi exception propagate nahi karta - sab ToolResult mein wrap hote hain.

        Example:
            >>> result = await orchestrator.execute_tool(
            ...     "pylint", {"file_path": "main.py"}, timeout=60, retries=1
            ... )
            >>> if result.success:
            ...     print(f"Found {len(result.data)} issues")
            ... else:
            ...     print(f"Failed: {result.error}")
        """
        # Step 1: Validate tool exists via helper
        if not self._is_tool_available(tool_name):
            available = list(self._tools.keys())
            error_msg = (
                f"Tool '{tool_name}' not found in registry. "
                f"Available: {available}"
            )
            logger.error(error_msg)
            result = ToolResult(
                tool_name=tool_name,
                success=False,
                data={},
                error=error_msg,
                execution_time=0.0,
            )
            self._record_execution(result)
            return result

        tool = self._get_tool(tool_name)
        total_attempts = retries + 1
        last_error: str = ""
        overall_start = time.time()
        last_execution_time = 0.0

        # Step 2: Attempt loop with retries
        # Har attempt ka result individually record hota hai (history + stats)
        for attempt in range(1, total_attempts + 1):
            attempt_start = time.time()
            try:
                logger.info(
                    "Executing tool '%s' (attempt %d/%d, timeout=%ds)",
                    tool_name, attempt, total_attempts, timeout,
                )

                # Execute with timeout protection
                raw_result = await asyncio.wait_for(
                    self._invoke_tool(tool, params),
                    timeout=timeout,
                )
                last_execution_time = time.time() - attempt_start

                # Normalize whatever tool returned into our ToolResult
                result = self._build_result(tool_name, raw_result, last_execution_time)

                # Success path - record this successful attempt
                self._record_execution(result)
                logger.info(
                    "Tool '%s' succeeded on attempt %d (%.2fs)",
                    tool_name, attempt, last_execution_time,
                )
                return result

            except asyncio.TimeoutError:
                last_execution_time = time.time() - attempt_start
                last_error = f"Timeout after {timeout}s"
                logger.warning(
                    "Tool '%s' timed out on attempt %d/%d (%.2fs elapsed)",
                    tool_name, attempt, total_attempts, last_execution_time,
                )
                # Record this failed attempt
                attempt_result = ToolResult(
                    tool_name=tool_name,
                    success=False,
                    data={},
                    error=f"Timeout after {timeout}s (attempt {attempt}/{total_attempts})",
                    execution_time=last_execution_time,
                )
                self._record_execution(attempt_result)

            except Exception as exc:
                last_execution_time = time.time() - attempt_start
                last_error = f"{type(exc).__name__}: {exc}"
                logger.exception(
                    "Tool '%s' failed on attempt %d/%d: %s",
                    tool_name, attempt, total_attempts, last_error,
                )
                # Record this failed attempt
                attempt_result = ToolResult(
                    tool_name=tool_name,
                    success=False,
                    data={},
                    error=f"{type(exc).__name__}: {exc} (attempt {attempt}/{total_attempts})",
                    execution_time=last_execution_time,
                )
                self._record_execution(attempt_result)

            # Wait before next retry (simple 1s delay per spec)
            if attempt < total_attempts:
                logger.debug(
                    "Waiting %ds before retry attempt %d",
                    self.RETRY_DELAY_SECONDS, attempt + 1,
                )
                await asyncio.sleep(self.RETRY_DELAY_SECONDS)

        # Step 3: All attempts failed - return summary result
        # Note: per-attempt records already in history, this summary is for caller
        total_elapsed = time.time() - overall_start
        summary_result = ToolResult(
            tool_name=tool_name,
            success=False,
            data={},
            error=f"Failed after {total_attempts} attempts. Last error: {last_error}",
            execution_time=total_elapsed,
        )

        logger.error(
            "Tool '%s' exhausted all %d attempts (total %.2fs)",
            tool_name, total_attempts, total_elapsed,
        )
        return summary_result

    async def execute_tools_parallel(
        self,
        tool_calls: List[Tuple[str, Dict[str, Any]]],
    ) -> List[ToolResult]:
        """
        Multiple tools ko simultaneously execute karo.
        asyncio.gather use karta hai - sab tools parallel chalte hain.

        Results input ke same order mein return hote hain.
        Individual tool failures gracefully handle hoti hain - ek tool fail
        hone se baqi affect nahi hote.

        Args:
            tool_calls: List of (tool_name, params) tuples.
                       Format: [("pylint", {"file": "x.py"}), ("bandit", {"file": "x.py"})]
                       Empty list valid hai (returns empty list).

        Returns:
            List of ToolResults in same order as input. Same length as input.

        Example:
            >>> results = await orchestrator.execute_tools_parallel([
            ...     ("pylint", {"file": "main.py"}),
            ...     ("bandit", {"file": "main.py"}),
            ...     ("flake8", {"file": "main.py"}),
            ... ])
            >>> for r in results:
            ...     status = "OK" if r.success else f"FAIL: {r.error}"
            ...     print(f"{r.tool_name}: {status}")
        """
        if not tool_calls:
            logger.warning("execute_tools_parallel called with empty list")
            return []

        logger.info("Executing %d tools in parallel", len(tool_calls))

        # Optionally convert tuples to ToolCall objects for internal processing
        # (tuples are more ergonomic for callers, ToolCall is more structured)
        typed_calls: List[ToolCall] = [
            ToolCall(tool_name=name, params=params)
            for name, params in tool_calls
        ]

        # Create tasks for all tool calls
        tasks = [
            self.execute_tool(call.tool_name, call.params)
            for call in typed_calls
        ]

        # Gather preserves order; our execute_tool catches all exceptions internally
        # return_exceptions=True is defensive - shouldn't see any
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Process results - replace any unexpected exceptions with error ToolResults
        final_results: List[ToolResult] = []
        for idx, result in enumerate(results):
            if isinstance(result, Exception):
                tool_name = typed_calls[idx].tool_name
                logger.error("Parallel task for %s raised: %s", tool_name, result)
                error_result = ToolResult(
                    tool_name=tool_name,
                    success=False,
                    data={},
                    error=f"Parallel execution error: {result}",
                    execution_time=0.0,
                )
                final_results.append(error_result)
            else:
                final_results.append(result)

        success_count = sum(1 for r in final_results if r.success)
        logger.info(
            "Parallel execution done: %d/%d succeeded",
            success_count, len(final_results),
        )
        return final_results

    # =========================================================================
    # RETRY MANAGEMENT
    # =========================================================================
    def should_retry_tool(self, tool_name: str) -> bool:
        """
        Check karo ke kya tool ko retry karna safe hai ya nahi.
        Failed tools counter check karta hai - agar consecutive failures
        RETRY_ATTEMPTS se kam hain to retry kar sakte hain.

        Args:
            tool_name: Tool identifier to check.

        Returns:
            True if tool can still be retried (failure count < RETRY_ATTEMPTS).
            False if already failed too many times.
            True also if tool has no recorded failures yet.

        Example:
            >>> if orchestrator.should_retry_tool("pylint"):
            ...     result = await orchestrator.execute_tool("pylint", params)
            ... else:
            ...     logger.warning("Pylint has failed too many times, switching tool")
        """
        with self._lock:
            failure_count = self._failed_tools.get(tool_name, 0)
            return failure_count < RETRY_ATTEMPTS

    def reset_tool_failures(self, tool_name: str) -> None:
        """
        Specific tool ka failure count reset karo.
        Allows retrying after manual failure clear.

        Useful jab:
        - External state change hua hai (jaise file fix ho gayi)
        - Manual intervention ke baad retry karna ho
        - Testing scenarios mein

        Args:
            tool_name: Tool identifier to reset.

        Returns:
            None

        Example:
            >>> orchestrator.reset_tool_failures("pylint")
            >>> # Ab pylint dobara try kar sakte hain
        """
        with self._lock:
            if tool_name in self._failed_tools:
                old_count = self._failed_tools[tool_name]
                self._failed_tools[tool_name] = 0
                logger.info(
                    "Reset failure count for '%s' (was %d)",
                    tool_name, old_count,
                )
            else:
                logger.debug(
                    "reset_tool_failures called for '%s' with no prior failures",
                    tool_name,
                )

    # =========================================================================
    # INSPECTION METHODS
    # =========================================================================
    def get_execution_history(self) -> List[ToolResult]:
        """
        Saari tool executions ka chronological history return karo.
        Returned list copy hai - modify karne se memory affect nahi hogi.

        Returns:
            List of ToolResults in execution order (oldest first).

        Example:
            >>> history = orchestrator.get_execution_history()
            >>> for h in history[-5:]:  # last 5 executions
            ...     print(f"{h.tool_name}: {h.execution_time:.2f}s")
        """
        with self._lock:
            return list(self._execution_history)

    def get_tool_stats(self) -> Dict[str, Any]:
        """
        Detailed statistics return karo - global aur per-tool dono.

        Output format (avg_time computed on-demand, not cached):
            {
                "total_executions": 5,
                "successful": 4,
                "failed": 1,
                "average_time": 2.3,
                "tools": {
                    "fetch_repository": {
                        "executions": 2,
                        "success": 2,
                        "avg_time": 1.5
                    },
                    "analyze_code": {
                        "executions": 3,
                        "success": 2,
                        "avg_time": 3.1
                    }
                }
            }

        Returns:
            Dict with global stats and per-tool breakdown.

        Example:
            >>> stats = orchestrator.get_tool_stats()
            >>> print(f"Total: {stats['total_executions']}")
            >>> print(f"Success rate: {stats['successful']/stats['total_executions']:.1%}")
            >>> for tool, t_stats in stats['tools'].items():
            ...     print(f"  {tool}: avg {t_stats['avg_time']:.2f}s")
        """
        with self._lock:
            total_executions = len(self._execution_history)
            successful = sum(1 for r in self._execution_history if r.success)
            failed = total_executions - successful
            total_time = sum(r.execution_time for r in self._execution_history)
            average_time = round(total_time / total_executions, 4) if total_executions > 0 else 0.0

            # Per-tool breakdown - compute avg_time on the fly
            tools_stats: Dict[str, Dict[str, Any]] = {}
            for tool_name, raw_stats in self._per_tool_stats.items():
                executions = raw_stats["executions"]
                total_tool_time = raw_stats["total_time"]
                avg_time = (
                    round(total_tool_time / executions, 4)
                    if executions > 0
                    else 0.0
                )
                tools_stats[tool_name] = {
                    "executions": executions,
                    "success": raw_stats["success"],
                    "avg_time": avg_time,
                }

            return {
                "total_executions": total_executions,
                "successful": successful,
                "failed": failed,
                "average_time": average_time,
                "tools": tools_stats,
            }

    def get_failed_tools(self) -> Dict[str, int]:
        """
        Tools jo currently failed state mein hain (with their failure counts).
        Useful for debugging aur retry strategy decisions.

        Returns:
            Dict mapping tool_name -> consecutive failure count.
            Empty dict if no tools have failed.

        Example:
            >>> failed = orchestrator.get_failed_tools()
            >>> if "pylint" in failed:
            ...     print(f"Pylint failed {failed['pylint']} times")
        """
        with self._lock:
            return dict(self._failed_tools)

    def reset_history(self) -> None:
        """
        Saari history aur state reset karo - new request ke liye.
        Yeh clear karta hai:
        - execution_history (saare past results)
        - failed_tools counter (saari failure counts)
        - per_tool_stats (per-tool statistics)
        - last_updated tracking

        Tools registry AFFECT nahi hota - registered tools rehte hain.
        Sirf execution state aur history clear hoti hai.

        Returns:
            None

        Example:
            >>> orchestrator.reset_history()
            >>> print(orchestrator.get_tool_stats())
            {'total_executions': 0, 'successful': 0, ...}
        """
        with self._lock:
            hist_count = len(self._execution_history)
            failed_count = len(self._failed_tools)
            stats_count = len(self._per_tool_stats)
            self._execution_history.clear()
            self._failed_tools.clear()
            self._per_tool_stats.clear()
            logger.info(
                "History reset: cleared %d executions, %d failed tools, %d tool stats",
                hist_count, failed_count, stats_count,
            )

    def __repr__(self) -> str:
        """
        Debug representation showing tools count and execution stats.
        Format: ToolOrchestrator(tools=5, executions=12, success=10)
        """
        with self._lock:
            total = len(self._execution_history)
            success = sum(1 for r in self._execution_history if r.success)
            return (
                f"ToolOrchestrator(tools={len(self._tools)}, "
                f"executions={total}, success={success})"
            )

    # =========================================================================
    # PRIVATE HELPERS
    # =========================================================================
    def _is_tool_available(self, tool_name: str) -> bool:
        """
        Check karo ke tool registry mein exist karta hai ya nahi.

        Args:
            tool_name: Tool identifier to check.

        Returns:
            True if tool is registered, False otherwise.

        Example:
            >>> if orchestrator._is_tool_available("pylint"):
            ...     print("Pylint is available")
        """
        with self._lock:
            return tool_name in self._tools

    def _get_tool(self, tool_name: str) -> Optional[Any]:
        """
        Tool object retrieve karo from registry.
        Na mile to None return karo (caller ko handle karna hoga).

        Args:
            tool_name: Tool identifier to look up.

        Returns:
            Tool instance ya None agar tool registered nahi hai.

        Example:
            >>> tool = orchestrator._get_tool("pylint")
            >>> if tool is None:
            ...     print("Pylint not available")
        """
        with self._lock:
            return self._tools.get(tool_name)

    def _record_execution(self, tool_result: ToolResult) -> None:
        """
        Tool execution ko record karo - history, stats, failure tracking.
        Yeh central method hai - saari state updates yahan se flow karte hain.

        Side effects:
        - Appends to execution_history
        - Updates per_tool_stats (executions, success, total_time)
        - Updates failed_tools (consecutive failure count, reset on success)

        Args:
            tool_result: ToolResult jo record karna hai.

        Returns:
            None

        Example:
            >>> result = ToolResult(tool_name="pylint", success=True, ...)
            >>> orchestrator._record_execution(result)
        """
        try:
            with self._lock:
                # Append to history
                self._execution_history.append(tool_result)

                tool_name = tool_result.tool_name
                execution_time = tool_result.execution_time

                # Update per-tool stats
                if tool_name not in self._per_tool_stats:
                    self._per_tool_stats[tool_name] = {
                        "executions": 0,
                        "success": 0,
                        "total_time": 0.0,
                    }

                stats = self._per_tool_stats[tool_name]
                stats["executions"] += 1
                stats["total_time"] += execution_time
                if tool_result.success:
                    stats["success"] += 1
                    # Reset consecutive failure count on success
                    if tool_name in self._failed_tools:
                        self._failed_tools[tool_name] = 0
                else:
                    # Increment consecutive failure count
                    self._failed_tools[tool_name] = (
                        self._failed_tools.get(tool_name, 0) + 1
                    )

                # Log the execution
                status = "SUCCESS" if tool_result.success else "FAILURE"
                logger.info(
                    "Recorded %s for tool '%s' (%.2fs)",
                    status, tool_name, execution_time,
                )
        except Exception as exc:
            logger.exception("Failed to record execution: %s", exc)

    async def _invoke_tool(self, tool: Any, params: Dict[str, Any]) -> Any:
        """
        Tool ko invoke karo - different tool types handle karta hai.
        BaseTool style (run method) aur plain callable dono support karta hai.
        Sync aur async run methods dono handle hote hain.
        """
        # BaseTool style - has async run method
        if hasattr(tool, "run"):
            result = tool.run(params)
            if asyncio.iscoroutine(result):
                return await result
            return result

        # Plain async function or callable
        if callable(tool):
            result = tool(params)
            if asyncio.iscoroutine(result):
                return await result
            return result

        raise TypeError(
            f"Tool {type(tool).__name__} is not callable and has no 'run' method"
        )

    def _build_result(
        self, tool_name: str, raw_result: Any, execution_time: float
    ) -> ToolResult:
        """
        Whatever the tool returned ko normalize karke ToolResult banao.
        Different tool return types handle karta hai.

        Supported return types:
        - ToolResult: use as-is (with tool_name and execution_time override)
        - dict: wrap as data
        - anything else: wrap in {"result": ...}
        """
        if isinstance(raw_result, ToolResult):
            return ToolResult(
                tool_name=tool_name,
                success=raw_result.success,
                data=raw_result.data,
                error=raw_result.error,
                execution_time=execution_time,
            )

        if isinstance(raw_result, dict):
            return ToolResult(
                tool_name=tool_name,
                success=True,
                data=raw_result,
                error=None,
                execution_time=execution_time,
            )

        return ToolResult(
            tool_name=tool_name,
            success=True,
            data={"result": raw_result},
            error=None,
            execution_time=execution_time,
        )
