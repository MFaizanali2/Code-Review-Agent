"""
Agent State Management - ReACT loop ke dauran agent ki poori state track karo.
Yeh thread-safe nahi hai; agar parallel agents chahiye to alag session_id use karo.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class StepType(str, Enum):
    """ReACT cycle ke char steps - Think/Act/Observe/Reflect."""
    THINK = "think"
    ACT = "act"
    OBSERVE = "observe"
    REFLECT = "reflect"


@dataclass
class Step:
    """ReACT cycle ka ek single step record."""
    type: StepType
    content: str
    timestamp: float = field(default_factory=time.time)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class AgentState:
    """
    Poore agent ki state - ek session ke liye.
    Yahan se ReACT loop current kahan hai, kya kiya, kya observe kiya
    sab track hota hai.
    """
    session_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    user_input: str = ""
    current_iteration: int = 0
    steps: list[Step] = field(default_factory=list)
    observations: list[dict[str, Any]] = field(default_factory=list)
    final_answer: str = ""
    error: str | None = None
    created_at: float = field(default_factory=time.time)

    def add_step(self, step_type: StepType, content: str, **metadata: Any) -> None:
        """Naya step record karo - chronological order maintain hota hai."""
        step = Step(type=step_type, content=content, metadata=metadata)
        self.steps.append(step)

    def add_observation(self, tool_name: str, result: Any) -> None:
        """Tool result ko structured form mein save karo for later analysis."""
        self.observations.append({
            "tool": tool_name,
            "result": result,
            "iteration": self.current_iteration,
        })

    def get_observations_text(self) -> str:
        """
        Saari observations ko ek text block mein convert karo.
        Yeh LLM ko context dene ke liye use hota hai.
        """
        if not self.observations:
            return "No observations yet."
        lines = []
        for obs in self.observations:
            lines.append(f"[Tool: {obs['tool']}] {obs['result']}")
        return "\n".join(lines)

    def get_thinking_history(self) -> list[str]:
        """Saare THINK steps ka trace return karo - debugging ke liye useful."""
        return [s.content for s in self.steps if s.type == StepType.THINK]

    def reset(self) -> None:
        """State ko fresh karo - same session_id rakhke naya task start karo."""
        self.steps.clear()
        self.observations.clear()
        self.current_iteration = 0
        self.final_answer = ""
        self.error = None
        self.user_input = ""


class StateManager:
    """
    Multiple sessions ke states manage karne ka helper.
    Production mein Redis ya DB based manager se replace hoga.
    """

    def __init__(self) -> None:
        self._states: dict[str, AgentState] = {}

    def create_state(self, user_input: str, session_id: str | None = None) -> AgentState:
        """Naya state banao ya existing session ka state wapas karo."""
        if session_id and session_id in self._states:
            state = self._states[session_id]
            state.reset()
            state.user_input = user_input
            return state
        state = AgentState(user_input=user_input)
        if session_id:
            state.session_id = session_id
        self._states[state.session_id] = state
        return state

    def get_state(self, session_id: str) -> AgentState | None:
        """Session ID se state retrieve karo."""
        return self._states.get(session_id)

    def delete_state(self, session_id: str) -> None:
        """Session ka state delete karo - memory free karne ke liye."""
        self._states.pop(session_id, None)

    def list_sessions(self) -> list[str]:
        """Saare active session IDs return karo - admin/debug ke liye."""
        return list(self._states.keys())
