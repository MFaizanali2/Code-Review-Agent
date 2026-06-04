"""
agent_memory.py - Agent ka memory management system.
Yeh file AgentMemory class define karti hai jo:
- Conversation history (AgentStep objects) ko store karti hai
- Tool results ko indexed form mein rakhti hai (naam se fast lookup)
- LLM ke liye formatted context generate karti hai

Memory design principles:
- Bounded: max_history se zyada steps nahi rahenge (FIFO eviction)
- Indexed: tool results naam se O(1) lookup
- Thread-safe: abhi threading.Lock; async migrate karna ho to asyncio.Lock
- Debuggable: __repr__, to_dict, get_summary methods se quick inspection

Production mein Redis ya DB se replace karna hoga, lekin interface same rahega.
"""

# =============================================================================
# IMPORTS
# =============================================================================
from __future__ import annotations

import logging
import threading
from datetime import datetime
from typing import Any, Dict, List, Optional

from agent.agent_types import AgentStep, StepType, ToolResult
from agent.constants import MEMORY_MAX_SIZE

logger = logging.getLogger(__name__)


# =============================================================================
# AGENT MEMORY CLASS
# =============================================================================
class AgentMemory:
    """
    Agent ka bounded in-memory storage system.
    Steps aur tool results dono manage karta hai with FIFO eviction policy.

    Yeh class agent ki poori conversation history hold karti hai aur
    LLM ko context provide karne ka kaam karti hai.

    Thread-safety:
        Abhi threading.RLock (reentrant) use kar rahe hain taake same thread
        multiple methods call kar sake without deadlock. Future mein async
        use ke liye asyncio.Lock se replace kiya ja sakta hai - interface
        change nahi hoga.

    Attributes:
        max_history: Maximum number of AgentSteps to retain
        step_count: Current number of stored steps (property)
        tool_count: Number of unique tools with results (property)

    Example:
        >>> from agent.agent_types import AgentStep, StepType
        >>> memory = AgentMemory(max_history=50)
        >>> step = AgentStep(step_number=1, step_type=StepType.THINK, thought="Start review")
        >>> memory.add_step(step)
        >>> print(memory)
        AgentMemory(steps=1, tools=0)
    """

    # LLM context window ke liye - kitne recent steps bhejne hain
    CONTEXT_WINDOW_SIZE: int = 5

    # Error messages truncate limit
    ERROR_PREVIEW_LENGTH: int = 100

    def __init__(self, max_history: int = MEMORY_MAX_SIZE) -> None:
        """
        AgentMemory instance initialize karo.

        Args:
            max_history: Maximum steps to retain. Default MEMORY_MAX_SIZE (100).
                        Isse zyada steps add hone pe oldest evict hoga (FIFO).

        Example:
            >>> memory = AgentMemory()                # default 100
            >>> memory = AgentMemory(max_history=50)  # custom limit
        """
        # Steps chronological order mein store - FIFO eviction
        self._steps: List[AgentStep] = []

        # Tool results indexed by tool name for O(1) lookup
        # Value list hai taake same tool multiple times call ho sake
        self._tool_results: Dict[str, List[ToolResult]] = {}

        # Configuration
        self._max_history: int = max_history

        # Lifecycle tracking
        self._created_at: datetime = datetime.now()
        self._last_updated: datetime = datetime.now()

        # Thread safety - RLock allows reentrant calls from same thread
        self._lock = threading.RLock()

        logger.info(
            "AgentMemory initialized: max_history=%d, created_at=%s",
            max_history, self._created_at.isoformat(),
        )

    # =========================================================================
    # PROPERTIES
    # =========================================================================
    @property
    def max_history(self) -> int:
        """Configured max history limit - read-only."""
        return self._max_history

    @property
    def step_count(self) -> int:
        """Current number of steps in memory (thread-safe)."""
        with self._lock:
            return len(self._steps)

    @property
    def tool_count(self) -> int:
        """Number of unique tools with stored results (thread-safe)."""
        with self._lock:
            return len(self._tool_results)

    @property
    def is_full(self) -> bool:
        """True if memory at max capacity."""
        return self.step_count >= self._max_history

    # =========================================================================
    # CORE METHODS - Adding data
    # =========================================================================
    def add_step(self, step: AgentStep) -> None:
        """
        Memory mein ek naya AgentStep add karo.
        Agar memory full ho jaye to oldest step evict hoga (FIFO policy).

        Yeh method thread-safe hai aur timestamps update karta hai.

        Args:
            step: AgentStep instance to add. step_number unique hona chahiye
                  taake debugging mein confusion na ho (validation nahi karta
                  - LLM/ReACT loop responsible hai).

        Returns:
            None

        Example:
            >>> step = AgentStep(step_number=1, step_type=StepType.THINK, thought="...")
            >>> memory.add_step(step)
        """
        try:
            with self._lock:
                self._steps.append(step)
                self._last_updated = datetime.now()

                # FIFO eviction - while loop for safety (kabhi kabhi multiple steps add)
                evicted_count = 0
                while len(self._steps) > self._max_history:
                    removed = self._steps.pop(0)
                    evicted_count += 1
                    logger.debug(
                        "Evicted step #%d (memory full, max=%d)",
                        removed.step_number, self._max_history,
                    )

                if evicted_count > 0:
                    logger.info("Memory full: evicted %d oldest step(s)", evicted_count)
                logger.debug(
                    "Step #%d added (current count=%d/%d)",
                    step.step_number, len(self._steps), self._max_history,
                )
        except Exception as exc:
            logger.exception("Failed to add step: %s", exc)

    def add_tool_result(self, tool_name: str, result: ToolResult) -> None:
        """
        Tool ka result memory mein store karo (indexed by tool name).
        Same tool multiple times call ho sakta hai - saare results retain honge.

        Args:
            tool_name: Tool ka unique identifier (registry key).
            result: ToolResult instance from tool execution.

        Returns:
            None

        Example:
            >>> result = ToolResult(tool_name="pylint", success=True, data={"issues": 3})
            >>> memory.add_tool_result("pylint", result)
            >>> # Same tool dobara call
            >>> memory.add_tool_result("pylint", another_result)  # list mein 2 results
        """
        if not tool_name:
            logger.warning("add_tool_result called with empty tool_name, ignoring")
            return

        try:
            with self._lock:
                # First time execution - initialize list
                if tool_name not in self._tool_results:
                    self._tool_results[tool_name] = []
                    logger.debug("First execution recorded for tool: %s", tool_name)

                self._tool_results[tool_name].append(result)
                self._last_updated = datetime.now()

                logger.debug(
                    "Tool result added: %s (total results for tool=%d)",
                    tool_name, len(self._tool_results[tool_name]),
                )
        except Exception as exc:
            logger.exception("Failed to add tool result for %s: %s", tool_name, exc)

    # =========================================================================
    # RETRIEVAL METHODS
    # =========================================================================
    def get_context_for_llm(self) -> str:
        """
        LLM ke liye formatted context string banao.
        Last 5 steps include karta hai with all their details (thought, action, result).

        Yeh method LLM ko "kya hua ab tak" batane ke liye use hota hai.
        Format readable hai - LLM easily parse kar sake.

        Returns:
            Formatted string with recent steps. Empty memory pe "No steps yet" return.

        Example output:
            === AGENT MEMORY CONTEXT ===

            Step 1:
              Type: THINK
              Thought: Fetch repository se start karte hain
              Action: fetch_repository
              Result: Success
        """
        try:
            with self._lock:
                if not self._steps:
                    return "=== AGENT MEMORY CONTEXT ===\n\nNo steps yet."

                # Last N steps - slicing efficient hai for list
                recent_steps = self._steps[-self.CONTEXT_WINDOW_SIZE:]

                lines: List[str] = ["=== AGENT MEMORY CONTEXT ===", ""]
                for step in recent_steps:
                    lines.append(f"Step {step.step_number}:")
                    lines.append(f"  Type: {step.step_type.value.upper()}")

                    if step.thought:
                        lines.append(f"  Thought: {step.thought}")

                    if step.action:
                        lines.append(f"  Action: {step.action.tool_name}")
                        if step.action.params:
                            params_str = self._format_params(step.action.params)
                            lines.append(f"  Params: {params_str}")

                    if step.observation:
                        if step.observation.success:
                            result_preview = self._format_data(step.observation.data)
                            lines.append(f"  Result: Success - {result_preview}")
                        else:
                            err = self._truncate_error(step.observation.error)
                            lines.append(f"  Result: Failed - {err}")

                    if step.reflection:
                        lines.append(f"  Reflection: {step.reflection}")

                    lines.append("")  # Blank line between steps

                return "\n".join(lines).rstrip()
        except Exception as exc:
            logger.exception("Failed to build LLM context: %s", exc)
            return f"=== AGENT MEMORY CONTEXT ===\n\nError building context: {exc}"

    def get_last_tool_result(self, tool_name: str) -> Optional[ToolResult]:
        """
        Kisi specific tool ka most recent result return karo.
        Agar tool kabhi execute nahi hua to None.

        Args:
            tool_name: Tool identifier to look up.

        Returns:
            Most recent ToolResult, ya None agar tool execute nahi hua.

        Example:
            >>> last = memory.get_last_tool_result("pylint")
            >>> if last and last.success:
            ...     print(f"Found {len(last.data)} issues")
        """
        try:
            with self._lock:
                results = self._tool_results.get(tool_name)
                return results[-1] if results else None
        except Exception as exc:
            logger.exception("Failed to get last result for %s: %s", tool_name, exc)
            return None

    def get_all_tool_results(self, tool_name: str) -> List[ToolResult]:
        """
        Specific tool ke saare historical results return karo.
        Returned list copy hai - modifying it won't affect memory.

        Args:
            tool_name: Tool identifier to look up.

        Returns:
            List of ToolResults (newest last), empty list if tool never ran.

        Example:
            >>> all_results = memory.get_all_tool_results("pylint")
            >>> success_rate = sum(1 for r in all_results if r.success) / len(all_results)
        """
        try:
            with self._lock:
                results = self._tool_results.get(tool_name, [])
                return list(results)  # Copy return karo - safe iteration
        except Exception as exc:
            logger.exception("Failed to get all results for %s: %s", tool_name, exc)
            return []

    def get_steps_by_type(self, step_type: StepType) -> List[AgentStep]:
        """
        Specific type ke saare steps return karo (THINK, ACT, OBSERVE, REFLECT).
        Debugging aur analysis ke liye useful.

        Args:
            step_type: StepType enum value to filter by.

        Returns:
            List of matching AgentSteps. Empty list if no matches.

        Example:
            >>> think_steps = memory.get_steps_by_type(StepType.THINK)
            >>> print(f"Agent sochnay mein {len(think_steps)} baar laga")
        """
        try:
            with self._lock:
                return [s for s in self._steps if s.step_type == step_type]
        except Exception as exc:
            logger.exception("Failed to filter steps by type %s: %s", step_type, exc)
            return []

    # =========================================================================
    # UTILITY METHODS
    # =========================================================================
    def clear(self) -> None:
        """
        Saari memory clear karo - steps aur tool results dono.
        Useful for new requests ya testing.

        Note: created_at preserve hota hai (memory object lifecycle),
        sirf content reset hota hai. last_updated update hota hai.

        Returns:
            None

        Example:
            >>> memory.clear()
            >>> print(memory)
            AgentMemory(steps=0, tools=0)
        """
        try:
            with self._lock:
                step_count = len(self._steps)
                tool_count = len(self._tool_results)
                self._steps.clear()
                self._tool_results.clear()
                self._last_updated = datetime.now()
                logger.info(
                    "Memory cleared: removed %d steps and %d tool result sets",
                    step_count, tool_count,
                )
        except Exception as exc:
            logger.exception("Failed to clear memory: %s", exc)

    def to_dict(self) -> Dict[str, Any]:
        """
        Memory ka snapshot dictionary mein convert karo.
        Logging, debugging, aur API responses ke liye useful.

        Returns:
            Dict with keys: step_count, tool_results_count, created_at, etc.

        Example:
            >>> snapshot = memory.to_dict()
            >>> import json
            >>> print(json.dumps(snapshot, indent=2))
        """
        try:
            with self._lock:
                total_results = sum(len(r) for r in self._tool_results.values())
                return {
                    "step_count": len(self._steps),
                    "tool_results_count": total_results,
                    "unique_tools_used": len(self._tool_results),
                    "tools_used": list(self._tool_results.keys()),
                    "max_history": self._max_history,
                    "memory_utilization": f"{len(self._steps)}/{self._max_history}",
                    "is_full": len(self._steps) >= self._max_history,
                    "created_at": self._created_at.isoformat(),
                    "last_updated": self._last_updated.isoformat(),
                }
        except Exception as exc:
            logger.exception("Failed to serialize memory: %s", exc)
            return {"error": str(exc)}

    def get_summary(self) -> str:
        """
        Memory ka human-readable summary banao.
        Quick inspection ke liye - logs ya UI mein dikhane ke liye.

        Returns:
            Summary string describing memory state.

        Example:
            >>> memory.get_summary()
            '5 steps completed. Tools used: fetch_repository, analyze_code'
        """
        try:
            with self._lock:
                step_count = len(self._steps)
                tool_names = list(self._tool_results.keys())
                tools_str = ", ".join(tool_names) if tool_names else "none"
                return f"{step_count} steps completed. Tools used: {tools_str}"
        except Exception as exc:
            logger.exception("Failed to generate summary: %s", exc)
            return f"Error generating summary: {exc}"

    def __repr__(self) -> str:
        """
        Debug-friendly string representation.
        Format: AgentMemory(steps=N, tools=M)
        """
        # Direct access without lock - safe for read-only fields
        # __repr__ shouldn't block or take locks
        return f"AgentMemory(steps={len(self._steps)}, tools={len(self._tool_results)})"

    def __len__(self) -> int:
        """len(memory) se current step count pata karo."""
        with self._lock:
            return len(self._steps)

    # =========================================================================
    # PRIVATE HELPERS
    # =========================================================================
    @staticmethod
    def _format_params(params: Dict[str, Any]) -> str:
        """
        Params dict ko readable string mein format karo.
        LLM context ke liye - zyada lambe values truncate karte hain.
        """
        try:
            parts: List[str] = []
            for k, v in params.items():
                v_str = str(v)
                if len(v_str) > 50:
                    v_str = v_str[:47] + "..."
                parts.append(f"{k}={v_str}")
            return ", ".join(parts) if parts else "none"
        except Exception:
            return "<unformattable>"

    @staticmethod
    def _format_data(data: Dict[str, Any]) -> str:
        """
        Tool result data ko compact string mein format karo.
        Useful one-liner for LLM context.
        """
        try:
            if not data:
                return "no data"
            # First 2 keys dikhao with their values
            items = list(data.items())[:2]
            parts = [f"{k}={v}" for k, v in items]
            extra = len(data) - len(items)
            summary = ", ".join(parts)
            if extra > 0:
                summary += f" (+{extra} more)"
            return summary
        except Exception:
            return "<data>"

    def _truncate_error(self, error: Optional[str]) -> str:
        """Error message ko truncate karo for readable context."""
        if not error:
            return "unknown error"
        if len(error) > self.ERROR_PREVIEW_LENGTH:
            return error[: self.ERROR_PREVIEW_LENGTH - 3] + "..."
        return error
