"""
ReACT Loop - Reason + Act pattern ka core implementation.
Yeh agent ka dimagh hai. Har step pe Think -> Act -> Observe -> Reflect cycle chalta hai.

Think    : LLM se poocho "kya karna hai, kyun karna hai"
Act      : Tool call karo ya final answer generate karo
Observe  : Tool ka result ya LLM ka output capture karo
Reflect  : Kya yeh answer sahi hai? Aur steps chahiye? Decide karo.
"""

from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from agent.core.state import AgentState, StepType
from agent.llm.client import LLMClient, LLMResponse
from agent.memory.conversation import ConversationMemory, MessageRole
from agent.prompts.system import (
    build_react_prompt,
    build_reflection_prompt,
    build_tool_selection_prompt,
)
from agent.tools.base import ToolResult
from agent.tools.registry import ToolRegistry

logger = logging.getLogger(__name__)


class LoopStatus(str, Enum):
    """ReACT loop ka final status - kya task complete hua ya nahi."""
    SUCCESS = "success"            # Final answer mil gaya
    MAX_ITERATIONS = "max_iterations"  # Limit hit ho gayi
    ERROR = "error"                # Koi exception aayi
    TIMEOUT = "timeout"            # Time limit khatam


@dataclass
class ReACTConfig:
    """ReACT loop ki configuration - easily tunable."""
    max_iterations: int = 8            # Zyada iterations = zyada cost, kam = kaam adhura
    timeout_seconds: int = 120         # Total time limit per task
    reflection_enabled: bool = True    # Reflect step on karo ya skip
    min_confidence: float = 0.7        # Is se kam confidence pe aur socho
    verbose: bool = False              # Debug logging on/off


@dataclass
class LoopResult:
    """ReACT loop ka final output - API/UI ko yeh return karte hain."""
    status: LoopStatus
    final_answer: str = ""
    iterations_used: int = 0
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    thinking_trace: list[str] = field(default_factory=list)
    error: str | None = None
    duration_seconds: float = 0.0


class ReACTLoop:
    """
    Main ReACT loop controller.
    Yeh class LLM, memory, aur tools ko orchestrate karke ek complete
    reasoning cycle chalaati hai.

    Usage:
        loop = ReACTLoop(llm, memory, registry, config)
        result = await loop.run("mere code mein bugs find karo")
    """

    def __init__(
        self,
        llm: LLMClient,
        memory: ConversationMemory,
        registry: ToolRegistry,
        config: ReACTConfig | None = None,
    ) -> None:
        self.llm = llm
        self.memory = memory
        self.registry = registry
        self.config = config or ReACTConfig()
        logger.info("ReACTLoop initialized with max_iterations=%d", self.config.max_iterations)

    async def run(self, user_input: str, session_id: str = "default") -> LoopResult:
        """
        Main entry point - user input lo aur ReACT cycle chalao.
        Yeh method complete task solve karke LoopResult return karta hai.
        """
        start_time = time.time()
        state = AgentState(session_id=session_id, user_input=user_input)
        self.memory.add_message(MessageRole.USER, user_input, session_id=session_id)

        tool_calls: list[dict[str, Any]] = []
        thinking_trace: list[str] = []

        try:
            for iteration in range(1, self.config.max_iterations + 1):
                # Timeout check - agar time khatam ho gaya to break
                if time.time() - start_time > self.config.timeout_seconds:
                    return self._finish(
                        state, LoopStatus.TIMEOUT, tool_calls, thinking_trace,
                        start_time, error="Timeout exceeded",
                    )

                logger.info("ReACT iteration %d/%d", iteration, self.config.max_iterations)
                state.current_iteration = iteration

                # Step 1: THINK - LLM se reasoning karwao
                thought = await self._think(state)
                thinking_trace.append(thought)
                state.add_step(StepType.THINK, thought)

                # Step 2: ACT - decide karo tool call karna hai ya final answer
                action = self._parse_action(thought)
                if action.get("type") == "final_answer":
                    answer = action.get("answer", "")
                    self.memory.add_message(MessageRole.ASSISTANT, answer, session_id=session_id)
                    return self._finish(
                        state, LoopStatus.SUCCESS, tool_calls, thinking_trace,
                        start_time, final_answer=answer,
                    )

                # Step 3: ACT - tool call execute karo
                tool_name = action.get("tool", "")
                tool_input = action.get("input", {})

                if not tool_name:
                    # LLM ne tool name nahi diya, reflect karwao
                    reflection = await self._reflect(state, "No tool selected")
                    thinking_trace.append(reflection)
                    continue

                observation = await self._act(state, tool_name, tool_input)
                tool_calls.append({"tool": tool_name, "input": tool_input, "result": observation})
                state.add_step(StepType.OBSERVE, str(observation))

                # Step 4: REFLECT - kya kaam ho gaya? Aur chahiye?
                if self.config.reflection_enabled:
                    reflection = await self._reflect(state, observation)
                    thinking_trace.append(reflection)
                    if reflection and self._should_stop_reflection(reflection):
                        # Reflection ne bola kaam ho gaya, final answer maango
                        final = await self._force_final_answer(state)
                        self.memory.add_message(MessageRole.ASSISTANT, final, session_id=session_id)
                        return self._finish(
                            state, LoopStatus.SUCCESS, tool_calls, thinking_trace,
                            start_time, final_answer=final,
                        )

            # Max iterations khatam
            final = await self._force_final_answer(state)
            self.memory.add_message(MessageRole.ASSISTANT, final, session_id=session_id)
            return self._finish(
                state, LoopStatus.MAX_ITERATIONS, tool_calls, thinking_trace,
                start_time, final_answer=final,
            )

        except Exception as exc:  # noqa: BLE001 - top level safety net
            logger.exception("ReACT loop failed: %s", exc)
            return self._finish(
                state, LoopStatus.ERROR, tool_calls, thinking_trace,
                start_time, error=str(exc),
            )

    async def _think(self, state: AgentState) -> str:
        """
        THINK step - LLM ko current state bhejo aur next reasoning maango.
        Yeh step decide karta hai ke agla kya karna hai.
        """
        tools_desc = self.registry.describe_all()
        prompt = build_react_prompt(
            user_input=state.user_input,
            history=self.memory.get_recent(state.session_id, limit=10),
            available_tools=tools_desc,
            observations=state.get_observations_text(),
            iteration=state.current_iteration,
        )
        response: LLMResponse = await self.llm.generate(prompt)
        logger.debug("Think step: %s", response.content[:200])
        return response.content

    async def _act(self, state: AgentState, tool_name: str, tool_input: dict[str, Any]) -> str:
        """
        ACT step - tool call execute karo aur result capture karo.
        Agar tool nahi mila to error observation return karo.
        """
        tool = self.registry.get(tool_name)
        if tool is None:
            msg = f"Tool '{tool_name}' not found in registry"
            logger.warning(msg)
            return f"ERROR: {msg}"

        logger.info("Executing tool: %s with input: %s", tool_name, tool_input)
        try:
            result: ToolResult = await tool.run(tool_input)
            observation = result.to_observation()
        except Exception as exc:  # noqa: BLE001
            logger.exception("Tool %s failed: %s", tool_name, exc)
            observation = f"ERROR in {tool_name}: {exc}"
        return observation

    async def _reflect(self, state: AgentState, observation: str) -> str:
        """
        REFLECT step - LLM se poocho "kya yeh sahi hai? task complete hua?"
        Yeh step unnecessary iterations bachata hai.
        """
        prompt = build_reflection_prompt(
            user_input=state.user_input,
            observation=observation,
            iteration=state.current_iteration,
            steps_so_far=len(state.steps),
        )
        response = await self.llm.generate(prompt)
        logger.debug("Reflect step: %s", response.content[:200])
        return response.content

    async def _force_final_answer(self, state: AgentState) -> str:
        """
        Jab max iterations ya timeout ho jaye, LLM se best possible answer maango.
        Yeh ensure karta hai ke user ko kuch na kuch jawab zarur mile.
        """
        prompt = build_tool_selection_prompt(
            user_input=state.user_input,
            observations=state.get_observations_text(),
            history=self.memory.get_recent(state.session_id, limit=10),
        )
        response = await self.llm.generate(prompt)
        return response.content

    def _parse_action(self, thought: str) -> dict[str, Any]:
        """
        LLM ke thought se action extract karo.
        Expected formats:
          - JSON block: {"type": "final_answer", "answer": "..."}
          - JSON block: {"type": "tool_call", "tool": "name", "input": {...}}
          - Plain text (fallback)
        """
        # Pehle JSON block try karo
        json_match = re.search(r"\{[\s\S]*\}", thought)
        if json_match:
            try:
                parsed = json.loads(json_match.group(0))
                if isinstance(parsed, dict):
                    return parsed
            except json.JSONDecodeError:
                pass

        # Fallback: "Final Answer:" prefix dhundho
        if "final answer:" in thought.lower():
            answer = thought.split(":", 1)[-1].strip()
            return {"type": "final_answer", "answer": answer}

        return {"type": "tool_call", "tool": "", "input": {}}

    def _should_stop_reflection(self, reflection: str) -> bool:
        """
        Reflection text dekho - agar LLM ne bola "task complete" to stop.
        Simple keyword check - more sophisticated logic Person 3 add kar sakta hai.
        """
        stop_keywords = ["task complete", "done", "sufficient", "no more steps needed", "final"]
        text = reflection.lower()
        return any(kw in text for kw in stop_keywords)

    def _finish(
        self,
        state: AgentState,
        status: LoopStatus,
        tool_calls: list[dict[str, Any]],
        thinking_trace: list[str],
        start_time: float,
        final_answer: str = "",
        error: str | None = None,
    ) -> LoopResult:
        """Helper - LoopResult banane ka clean tarika."""
        return LoopResult(
            status=status,
            final_answer=final_answer,
            iterations_used=state.current_iteration,
            tool_calls=tool_calls,
            thinking_trace=thinking_trace,
            error=error,
            duration_seconds=time.time() - start_time,
        )
