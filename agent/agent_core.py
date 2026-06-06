"""
agent_core.py - Main ReACT loop agent implementation.
Yeh file CodeReviewAgent class define karti hai jo complete
Think -> Act -> Observe -> Reflect cycle chalaati hai.

Architecture:
    ReviewRequest -> CodeReviewAgent.run()
                          |
                          v
                    [ReACT Loop]
                          |
        +-----------------+-----------------+
        |                 |                 |
        v                 v                 v
    _think_step      _act_step        _observe_step
    (LLM call)       (tool selection) (tool execution)
                          |                 |
                          +---->_reflect_step
                                     |
                                     v
                            _generate_final_result
                                     |
                                     v
                                ReviewResult
"""

# =============================================================================
# IMPORTS
# =============================================================================
import logging
import re
import time
from typing import Any, Dict, List, Optional, Tuple

from agent.agent_memory import AgentMemory
from agent.agent_orchestrator import ToolOrchestrator
from agent.agent_types import (
    AgentStatus,
    AgentStep,
    ReviewRequest,
    ReviewResult,
    StepType,
    ToolCall,
    ToolResult,
)
from agent.constants import MAX_STEPS
from agent.utils import (
    AVAILABLE_TOOL_NAMES,
    extract_tool_name_from_thought,
    format_tool_result_for_llm,
    get_current_timestamp,
    should_continue_loop,
    validate_review_request,
)

logger = logging.getLogger(__name__)


# =============================================================================
# PROMPT TEMPLATES - centralized yahan taake easy to tune
# =============================================================================
THINK_PROMPT_TEMPLATE = """You are a code review agent.

CONTEXT: {context}

REQUEST: {analysis_type}

AVAILABLE TOOLS:
1. fetch_repository - Download code from GitHub
2. analyze_code_structure - Analyze code structure
3. security_audit - Check security issues
4. performance_analysis - Check performance issues
5. generate_report - Create final report

DECIDE:
- What tool to use next? (or "DONE" if finished)
- Why?

Format:
NEXT_TOOL: [tool_name or DONE]
REASON: [Brief reason]
"""


# =============================================================================
# MAIN AGENT CLASS
# =============================================================================
class CodeReviewAgent:
    """
    Main ReACT loop agent for code review tasks.

    Yeh class:
    - LLM client (Person 3) se reasoning leti hai
    - Tools (Person 2) ko orchestrate karti hai
    - Memory maintain karti hai across steps
    - Final ReviewResult generate karti hai

    Lifecycle:
        1. Constructor: LLM aur tools ke saath initialize
        2. run(request): ReACT loop chalaao (main entry point)
        3. Step by step: Think -> Act -> Observe -> Reflect
        4. Final: Report generate karke wapas karo

    Example:
        >>> agent = CodeReviewAgent(llm_client=my_llm, tools_registry={...})
        >>> request = ReviewRequest(github_url="https://github.com/user/repo")
        >>> result = await agent.run(request)
        >>> print(result.quality_score)
    """

    def __init__(
        self,
        llm_client: Any,
        tools_registry: Dict[str, Any],
    ) -> None:
        """
        CodeReviewAgent initialize karo.

        Args:
            llm_client: LLM client instance (Person 3 provide karega).
                       Should have async `generate(prompt) -> response` method
                       where response has `.content` attribute.
            tools_registry: Dict of tool name -> tool instance.
                           Tool instances ka async `run(params)` method hona chahiye.

        Example:
            >>> agent = CodeReviewAgent(
            ...     llm_client=GeminiClient(),
            ...     tools_registry={"fetch_repository": fetch_tool, ...}
            ... )
        """
        # External dependencies
        self.llm_client = llm_client
        self.orchestrator = ToolOrchestrator(tools_registry)
        self.memory = AgentMemory()

        # Internal state
        self.status: AgentStatus = AgentStatus.IDLE
        self.current_step: int = 0
        self.current_request: Optional[ReviewRequest] = None
        self._started_at: Optional[float] = None

        # Available tools list (for LLM prompt + validation)
        # Empty registry means no tools - user is in control
        self.available_tools: List[str] = list(tools_registry.keys())

        logger.info(
            "CodeReviewAgent initialized with %d tools: %s",
            len(tools_registry), self.available_tools,
        )

    # =========================================================================
    # MAIN ENTRY POINT
    # =========================================================================
    async def run(
        self,
        request: ReviewRequest,
        max_steps: int = MAX_STEPS,
    ) -> ReviewResult:
        """
        Complete ReACT loop chalaao - main public method.

        Flow per iteration:
            1. THINK: LLM se poocho agla kya karna hai
            2. ACT: Tool call create karo (ya stop if DONE)
            3. OBSERVE: Tool execute karo, result capture karo
            4. REFLECT: Observation analyze karo, next decide karo
            5. Sab steps memory mein store karo

        Args:
            request: ReviewRequest with github_url/code_content + analysis_type.
            max_steps: Maximum ReACT iterations (default MAX_STEPS=10).

        Returns:
            ReviewResult with quality_score, issues, report, steps_taken, etc.

        Example:
            >>> request = ReviewRequest(
            ...     github_url="https://github.com/user/repo",
            ...     analysis_type="full"
            ... )
            >>> result = await agent.run(request)
            >>> print(f"Score: {result.quality_score}/10")
            >>> print(result.report)
        """
        # Validate request first - fail fast
        is_valid, error = validate_review_request(request)
        if not is_valid:
            logger.error("Invalid review request: %s", error)
            return ReviewResult(
                success=False,
                quality_score=0.0,
                issues=[],
                report=f"# Invalid Request\n\n{error}",
                steps_taken=0,
                execution_time=0.0,
                errors=[error or "Invalid request"],
            )

        # Reset state for new run
        self._reset_state()
        self.current_request = request
        start_time = time.time()
        self._started_at = start_time

        logger.info(
            "Starting ReACT loop: request_id=%s, max_steps=%d, analysis=%s",
            request.request_id, max_steps, request.analysis_type,
        )

        # Main ReACT loop
        try:
            for step_num in range(1, max_steps + 1):
                logger.info("=== ReACT Step %d/%d ===", step_num, max_steps)

                # STEP 1: THINK
                self.status = AgentStatus.THINKING
                thought, should_continue = await self._think_step(request)
                logger.info("THOUGHT: %s", thought[:200])

                if not should_continue:
                    logger.info("Agent signaled DONE - exiting loop")
                    break

                # Commit to this step only after we know we'll do work
                self.current_step = step_num

                # STEP 2: ACT
                self.status = AgentStatus.ACTING
                tool_call = await self._act_step(thought, step_num)
                if tool_call is None:
                    # Tool invalid - record and continue
                    logger.warning("No valid tool call generated, continuing")
                    self.memory.add_step(AgentStep(
                        step_number=step_num,
                        step_type=StepType.ACT,
                        thought=thought,
                        action=None,
                        observation=None,
                        reflection="No valid tool selected - retrying",
                    ))
                    continue

                # STEP 3: OBSERVE
                self.status = AgentStatus.OBSERVING
                observation = await self._observe_step(tool_call)

                # STEP 4: REFLECT
                self.status = AgentStatus.REFLECTING
                reflection = await self._reflect_step(observation, step_num)

                # Store complete step in memory
                self.memory.add_step(AgentStep(
                    step_number=step_num,
                    step_type=StepType.OBSERVE,
                    thought=thought,
                    action=tool_call,
                    observation=observation,
                    reflection=reflection,
                ))

                logger.info(
                    "Step %d complete: tool=%s, success=%s",
                    step_num, tool_call.tool_name, observation.success,
                )

            # Generate final result
            self.status = AgentStatus.COMPLETED
            result = await self._generate_final_result(request)
            result.steps_taken = self.current_step
            result.execution_time = time.time() - start_time

            logger.info(
                "ReACT loop complete: steps=%d, success=%s, score=%.1f",
                result.steps_taken, result.success, result.quality_score,
            )
            return result

        except Exception as exc:
            # Top-level safety net - never let agent crash
            self.status = AgentStatus.FAILED
            logger.exception("ReACT loop failed: %s", exc)
            return ReviewResult(
                success=False,
                quality_score=0.0,
                issues=[],
                report=f"# Agent Error\n\nAn unexpected error occurred: {exc}",
                steps_taken=self.current_step,
                execution_time=time.time() - start_time,
                errors=[str(exc)],
            )

    # =========================================================================
    # PRIVATE: THINK STEP
    # =========================================================================
    async def _think_step(self, request: ReviewRequest) -> Tuple[str, bool]:
        """
        STEP 1: Agent thinks about what to do next.

        LLM ko context, request details, aur available tools dikhata hai.
        LLM response parse karke next tool extract karta hai.

        Args:
            request: Current ReviewRequest being processed.

        Returns:
            Tuple of (thought_text, should_continue).
            - thought_text: Raw LLM response (for logging/debugging)
            - should_continue: False if LLM signaled DONE, True otherwise
        """
        try:
            # Build context from memory
            context = self.memory.get_context_for_llm()

            # Build prompt
            prompt = THINK_PROMPT_TEMPLATE.format(
                context=context,
                analysis_type=request.analysis_type,
            )

            logger.debug("Think prompt: %s", prompt[:200])

            # Call LLM
            response = await self.llm_client.generate(prompt)
            thought_text = getattr(response, "content", str(response))

            # Parse NEXT_TOOL from response
            next_tool = self._parse_next_tool(thought_text)

            # Decide if we should continue
            if next_tool is None or next_tool.upper() == "DONE":
                logger.info("LLM signaled completion")
                return thought_text, False

            # Validate the tool is in our available list
            if next_tool not in self.available_tools:
                logger.warning(
                    "LLM suggested unknown tool '%s' - continuing anyway",
                    next_tool,
                )
                # Continue - the next _act_step will handle invalid tools

            logger.debug("Next tool: %s", next_tool)
            return thought_text, True

        except Exception as exc:
            logger.exception("Think step failed: %s", exc)
            # On failure, return empty thought and stop (safe default)
            return f"Error in think step: {exc}", False

    def _parse_next_tool(self, thought: str) -> Optional[str]:
        """
        LLM response se NEXT_TOOL extract karo.
        Expected format: "NEXT_TOOL: tool_name" ya "NEXT_TOOL: DONE"

        Args:
            thought: LLM ka raw response text.

        Returns:
            Extracted tool name, "DONE", ya None agar parse na ho.
        """
        if not thought:
            return None

        # Primary: look for NEXT_TOOL: pattern
        match = re.search(
            r"NEXT_TOOL:\s*([A-Za-z_][A-Za-z0-9_]*)",
            thought,
            re.IGNORECASE,
        )
        if match:
            return match.group(1).strip()

        # Fallback: try to extract any known tool name from text
        return extract_tool_name_from_thought(thought, self.available_tools)

    # =========================================================================
    # PRIVATE: ACT STEP
    # =========================================================================
    async def _act_step(
        self, thought: str, step_num: int
    ) -> Optional[ToolCall]:
        """
        STEP 2: Agent takes action - tool call create karta hai.

        Thought text se tool name extract karta hai, parameters build karta hai,
        aur ToolCall object banata hai.

        Args:
            thought: Previous step ka thought text.
            step_num: Current step number (logging ke liye).

        Returns:
            ToolCall instance ya None agar tool invalid hai.
        """
        try:
            # Extract tool name from thought
            tool_name = extract_tool_name_from_thought(
                thought, self.available_tools
            )
            if tool_name is None:
                logger.warning("Could not extract tool name from thought")
                return None

            # Validate tool exists
            if not self.orchestrator._is_tool_available(tool_name):
                logger.error("Tool '%s' not available in orchestrator", tool_name)
                return None

            # Build parameters based on tool type
            params = self._build_tool_params(tool_name)
            if params is None:
                logger.error("Could not build params for tool '%s'", tool_name)
                return None

            tool_call = ToolCall(tool_name=tool_name, params=params)
            logger.info(
                "Step %d ACT: tool=%s, params=%s",
                step_num, tool_name, params,
            )
            return tool_call

        except Exception as exc:
            logger.exception("Act step failed: %s", exc)
            return None

    def _build_tool_params(self, tool_name: str) -> Optional[Dict[str, Any]]:
        """
        Tool ke liye parameters build karo based on tool type and context.

        Different tools ko different params chahiye:
        - fetch_repository: github_url ya code_content
        - analyze/security/performance: file paths from previous fetch
        - generate_report: no params

        Args:
            tool_name: Tool jiske liye params banane hain.

        Returns:
            Params dict ya None agar required context missing hai.
        """
        if self.current_request is None:
            return None

        if tool_name == "fetch_repository":
            return self._params_for_fetch()
        elif tool_name in ("analyze_code_structure", "security_audit", "performance_analysis"):
            return self._params_for_analyzer(tool_name)
        elif tool_name == "generate_report":
            return {}  # No params needed
        else:
            # Unknown tool - return empty params
            return {}

    def _params_for_fetch(self) -> Optional[Dict[str, Any]]:
        """fetch_repository ke liye params - URL ya code content."""
        if self.current_request is None:
            return None
        if self.current_request.github_url:
            return {"github_url": self.current_request.github_url}
        if self.current_request.code_content:
            return {"code_content": self.current_request.code_content}
        # Validation should have caught this already
        return None

    def _params_for_analyzer(self, tool_name: str) -> Dict[str, Any]:
        """
        Analysis tools ke liye params - file paths from previous fetch result.

        Agar fetch_repository pehle se run ho chuki hai to uske data se
        file paths use karte hain. Otherwise direct code_content.
        """
        if self.current_request is None:
            return {}

        # Pehle fetch_repository ka result dekho
        last_fetch = self.memory.get_last_tool_result("fetch_repository")
        if last_fetch and last_fetch.success and isinstance(last_fetch.data, dict):
            files = last_fetch.data.get("files", [])
            if files:
                return {"files": files, "tool": tool_name}

        # Fallback: direct code content
        if self.current_request.code_content:
            return {
                "code_content": self.current_request.code_content,
                "tool": tool_name,
            }

        return {"tool": tool_name}

    # =========================================================================
    # PRIVATE: OBSERVE STEP
    # =========================================================================
    async def _observe_step(self, tool_call: ToolCall) -> ToolResult:
        """
        STEP 3: Agent observes the tool execution result.

        Orchestrator ke through tool execute karta hai aur result memory mein
        store karta hai.

        Args:
            tool_call: ToolCall jo execute karna hai.

        Returns:
            ToolResult - success ya failure dono cases mein proper result.
        """
        try:
            logger.info(
                "OBSERVE: executing tool '%s' with params %s",
                tool_call.tool_name, tool_call.params,
            )

            # Execute through orchestrator (handles retries, timeouts)
            result = await self.orchestrator.execute_tool(
                tool_call.tool_name,
                tool_call.params,
            )

            # Log result clearly
            if result.success:
                logger.info(
                    "Tool '%s' succeeded in %.2fs",
                    tool_call.tool_name, result.execution_time,
                )
            else:
                logger.warning(
                    "Tool '%s' failed: %s",
                    tool_call.tool_name, result.error,
                )

            # Store in memory for later reference
            self.memory.add_tool_result(tool_call.tool_name, result)

            return result

        except Exception as exc:
            # Should not happen (orchestrator catches exceptions)
            # but safety net
            logger.exception("Observe step crashed: %s", exc)
            return ToolResult(
                tool_name=tool_call.tool_name,
                success=False,
                data={},
                error=f"Observe step exception: {exc}",
                execution_time=0.0,
            )

    # =========================================================================
    # PRIVATE: REFLECT STEP
    # =========================================================================
    async def _reflect_step(
        self, observation: ToolResult, step_num: int
    ) -> str:
        """
        STEP 4: Agent reflects on the observation.

        Decide karta hai ke aage kya karna hai:
        - Observation successful -> continue with next analysis
        - Observation failed -> try different approach
        - Sufficient data -> prepare to generate report

        Args:
            observation: Previous step ka ToolResult.
            step_num: Current step number.

        Returns:
            Reflection text (logged + stored in memory).
        """
        try:
            tool_name = observation.tool_name
            exec_time = observation.execution_time

            if observation.success:
                # Success - check what kind of tool
                if tool_name == "generate_report":
                    reflection = (
                        f"Step {step_num}: Report generated successfully "
                        f"in {exec_time:.1f}s. Task complete."
                    )
                else:
                    data_summary = format_tool_result_for_llm(observation)
                    reflection = (
                        f"Step {step_num}: Tool '{tool_name}' returned data. "
                        f"Continuing analysis with next tool."
                    )
            else:
                # Failure
                reflection = (
                    f"Step {step_num}: Tool '{tool_name}' failed "
                    f"({observation.error}). Will try different approach."
                )

            logger.info("REFLECT: %s", reflection)
            return reflection

        except Exception as exc:
            logger.exception("Reflect step failed: %s", exc)
            return f"Step {step_num}: Reflection error - {exc}"

    # =========================================================================
    # PRIVATE: GENERATE FINAL RESULT
    # =========================================================================
    async def _generate_final_result(
        self, request: ReviewRequest
    ) -> ReviewResult:
        """
        Sab collected data se final ReviewResult generate karo.

        - All tool results aggregate karta hai
        - Issues collect karta hai (har tool ke data se)
        - Quality score calculate karta hai
        - Markdown report generate karta hai

        Args:
            request: Original ReviewRequest (context ke liye).

        Returns:
            Complete ReviewResult with all fields populated.
        """
        try:
            logger.info("Generating final result from all tool results")

            # Collect all successful tool results
            all_results = self.orchestrator.get_execution_history()
            successful_results = [r for r in all_results if r.success]

            # Aggregate issues from all tools
            issues: List[Dict[str, Any]] = []
            for result in successful_results:
                if isinstance(result.data, dict) and "issues" in result.data:
                    tool_issues = result.data["issues"]
                    if isinstance(tool_issues, list):
                        issues.extend(tool_issues)

            # Calculate quality score: start at 10, deduct per issue
            # Capped at 0, floored at 0
            quality_score = max(0.0, 10.0 - min(len(issues), 10))

            # Determine overall success
            had_critical_failure = any(
                not r.success and r.tool_name == "fetch_repository"
                for r in all_results
            )

            # Generate markdown report
            report = self._format_report(
                request=request,
                all_results=all_results,
                successful_results=successful_results,
                issues=issues,
                quality_score=quality_score,
            )

            return ReviewResult(
                success=not had_critical_failure,
                quality_score=quality_score,
                issues=issues,
                report=report,
                steps_taken=self.current_step,
                execution_time=0.0,  # filled by run()
                errors=None,
            )

        except Exception as exc:
            logger.exception("Final result generation failed: %s", exc)
            return ReviewResult(
                success=False,
                quality_score=0.0,
                issues=[],
                report=f"# Report Generation Error\n\n{exc}",
                steps_taken=self.current_step,
                execution_time=0.0,
                errors=[str(exc)],
            )

    def _format_report(
        self,
        request: ReviewRequest,
        all_results: List[ToolResult],
        successful_results: List[ToolResult],
        issues: List[Dict[str, Any]],
        quality_score: float,
    ) -> str:
        """
        Markdown report generate karo from collected data.

        Sections:
        - Header (request info, score)
        - Summary
        - Issues (detailed)
        - Tool execution log
        - Recommendations
        """
        lines: List[str] = []

        # Header
        lines.append("# Code Review Report")
        lines.append("")
        lines.append(f"**Generated:** {get_current_timestamp().isoformat()}")
        lines.append(f"**Request ID:** {request.request_id}")
        lines.append(f"**Analysis Type:** {request.analysis_type}")
        if request.github_url:
            lines.append(f"**Repository:** {request.github_url}")
        lines.append("")

        # Score section
        lines.append("## Quality Score")
        lines.append("")
        score_emoji = "🟢" if quality_score >= 8 else "🟡" if quality_score >= 5 else "🔴"
        lines.append(f"**{score_emoji} {quality_score:.1f}/10**")
        lines.append("")
        if quality_score >= 8:
            lines.append("> Code quality is high. Minor improvements only.")
        elif quality_score >= 5:
            lines.append("> Code has some issues that should be addressed.")
        else:
            lines.append("> Code has significant issues requiring attention.")
        lines.append("")

        # Issues section
        lines.append(f"## Issues Found ({len(issues)})")
        lines.append("")
        if issues:
            # Group by severity if available
            by_severity: Dict[str, List[Dict[str, Any]]] = {}
            for issue in issues:
                severity = str(issue.get("severity", "unknown")).lower()
                by_severity.setdefault(severity, []).append(issue)

            for severity in ("critical", "high", "medium", "low", "unknown"):
                sev_issues = by_severity.get(severity, [])
                if sev_issues:
                    lines.append(f"### {severity.title()} ({len(sev_issues)})")
                    lines.append("")
                    for issue in sev_issues[:20]:  # cap at 20 per severity
                        title = issue.get("title") or issue.get("message") or str(issue)
                        file_path = issue.get("file", "")
                        line_num = issue.get("line", "")
                        location = f" `{file_path}:{line_num}`" if file_path else ""
                        lines.append(f"- {title}{location}")
                    if len(sev_issues) > 20:
                        lines.append(f"- ... and {len(sev_issues) - 20} more")
                    lines.append("")
        else:
            lines.append("✅ No issues identified.")
            lines.append("")

        # Tool executions
        lines.append("## Tool Executions")
        lines.append("")
        lines.append("| Tool | Status | Time |")
        lines.append("|------|--------|------|")
        for r in all_results:
            status = "✅ Success" if r.success else "❌ Failed"
            lines.append(f"| {r.tool_name} | {status} | {r.execution_time:.2f}s |")
        lines.append("")

        # Summary stats
        lines.append("## Summary")
        lines.append("")
        lines.append(f"- **Total tool executions:** {len(all_results)}")
        lines.append(f"- **Successful:** {len(successful_results)}")
        lines.append(f"- **Failed:** {len(all_results) - len(successful_results)}")
        lines.append(f"- **ReACT iterations:** {self.current_step}")
        lines.append("")

        return "\n".join(lines)

    # =========================================================================
    # UTILITY METHODS
    # =========================================================================
    def _reset_state(self) -> None:
        """Agent state reset karo for new request."""
        self.status = AgentStatus.IDLE
        self.current_step = 0
        self.current_request = None
        self._started_at = None
        # Memory aur orchestrator bhi reset
        self.memory.clear()
        self.orchestrator.reset_history()
        logger.debug("Agent state reset for new request")

    def get_status(self) -> AgentStatus:
        """Current agent status (for monitoring/UI)."""
        return self.status

    @property
    def tool_count(self) -> int:
        """Number of tools available to this agent (property)."""
        return len(self.available_tools)

    def get_memory_summary(self) -> str:
        """Memory ka quick summary (debugging/UI ke liye)."""
        return self.memory.get_summary()

    def __repr__(self) -> str:
        """Debug representation."""
        return (
            f"CodeReviewAgent(status={self.status.value}, "
            f"step={self.current_step}, "
            f"tools={len(self.available_tools)})"
        )
