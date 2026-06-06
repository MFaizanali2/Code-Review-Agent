"""
agent_types.py - Agent ke liye saari data type definitions.
Yeh file pure data shapes define karti hai - koi logic nahi, sirf structure.
Production mein yeh types API contract ban jaate hain between modules.

This file is the single source of truth for:
- ReACT loop step identifiers
- Tool execution request/response shapes
- Complete agent step records
- User request format
- Final review output format

Rule: Yahan sirf dataclasses aur enums hain - business logic nahi.
"""

# =============================================================================
# IMPORTS - sab imports top pe (PEP 8 compliant)
# =============================================================================
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================
def _utcnow() -> datetime:
    """
    Timezone-aware UTC timestamp generate karo.
    Production ke liye consistent timezone zaroori hai - naive datetime
    comparison bugs create karta hai across servers.
    """
    return datetime.now(timezone.utc)


# =============================================================================
# ENUMS
# =============================================================================
class StepType(str, Enum):
    """
    ReACT loop ke char steps ko identify karta hai.
    Think -> Act -> Observe -> Reflect cycle ke liye type-safe identifiers.

    Inherits from str taake JSON serialization mein direct use ho sake
    bina .value call kiye.

    Example:
        >>> step = StepType.THINK
        >>> print(step.value)
        'think'
        >>> step == StepType.ACT
        False
    """
    THINK = "think"      # LLM soch raha hai kya karna hai
    ACT = "act"          # Tool call ya final answer generate ho raha hai
    OBSERVE = "observe"  # Tool ka result ya LLM output capture ho raha hai
    REFLECT = "reflect"  # LLM evaluate kar raha hai kya kaam ho gaya


class AgentStatus(str, Enum):
    """
    Agent ka high-level lifecycle status.
    UI dashboards aur monitoring ke liye use hota hai.

    ReACT loop ke dauran status transitions:
        IDLE -> THINKING -> ACTING -> OBSERVING -> REFLECTING
              -> THINKING (next iteration) -> ... -> COMPLETED/FAILED

    Inherits from str for JSON serialization.

    Example:
        >>> status = AgentStatus.IDLE
        >>> status.value
        'idle'
        >>> status == AgentStatus.THINKING
        False
    """
    IDLE = "idle"              # Koi request nahi, input ka intezaar
    THINKING = "thinking"      # LLM se reasoning le raha hai
    ACTING = "acting"          # Tool call create/execute kar raha hai
    OBSERVING = "observing"    # Tool ka result analyze kar raha hai
    REFLECTING = "reflecting"  # Result pe self-evaluate kar raha hai
    COMPLETED = "completed"    # Task successfully complete
    FAILED = "failed"          # Error ya unrecoverable failure


# =============================================================================
# DATACLASSES - Tool execution
# =============================================================================
@dataclass
class ToolCall:
    """
    Ek tool execution request ko represent karta hai.
    Jab LLM decide karta hai ke koi tool chahiye, to yeh structure banta hai.

    Yeh dataclass:
    - Orchestrator ko batati hai ke konsa tool call karna hai
    - Params dict flexible hai - har tool ke apne parameters
    - Timestamp debugging aur tracing ke liye
    - call_id har call uniquely identify karta hai (logs/correlation ke liye)

    Example:
        >>> call = ToolCall(
        ...     tool_name="pylint_runner",
        ...     params={"file_path": "src/main.py", "severity": "error"}
        ... )
        >>> call.tool_name
        'pylint_runner'
    """
    tool_name: str                              # Konsa tool invoke karna hai (registry key)
    params: dict[str, Any] = field(default_factory=dict)  # Tool ke arguments - flexible dict
    timestamp: datetime = field(default_factory=_utcnow)  # Kab call generate hua
    call_id: str = field(default_factory=lambda: str(uuid.uuid4()))  # Unique ID for tracing

    def __repr__(self) -> str:
        """Debug-friendly representation - parameters ko readable rakhte hain."""
        return f"ToolCall(tool={self.tool_name!r}, params={self.params!r})"


@dataclass
class ToolResult:
    """
    Tool execution ke baad ka result store karta hai.
    Chahe tool success ho ya fail, structure same rehta hai.

    Fields semantics:
    - success: True if tool ne apna kaam kiya, False otherwise
    - data: Tool ka actual output (jo bhi shape tool return kare)
    - error: Agar failure hui to error message (success pe None)
    - execution_time: Seconds mein kitna time laga (performance tracking)
    - timestamp: Kab result generate hua

    Example:
        >>> result = ToolResult(
        ...     tool_name="pylint_runner",
        ...     success=True,
        ...     data={"issues": 3, "score": 8.5},
        ...     execution_time=1.23
        ... )
        >>> result.success
        True
    """
    tool_name: str                              # Kis tool ka result hai (call ke saath match karta hai)
    success: bool                                # Tool kamyab hua ya nahi
    data: dict[str, Any] = field(default_factory=dict)  # Tool ka actual output data
    error: str | None = None                     # Error message agar fail hua to
    execution_time: float = 0.0                  # Seconds mein execution duration
    timestamp: datetime = field(default_factory=_utcnow)  # Kab result ready hua

    def __repr__(self) -> str:
        """Debug representation - success/failure pehle dikhata hai."""
        return (
            f"ToolResult(tool={self.tool_name!r}, "
            f"success={self.success}, error={self.error!r})"
        )


# =============================================================================
# DATACLASSES - ReACT loop steps
# =============================================================================
@dataclass
class AgentStep:
    """
    ReACT cycle ka ek complete step record karta hai.
    Ek step mein Think, Act, Observe, Reflect chaarou ho sakte hain (ya kuch subset).

    Yeh dataclass history/audit ke liye use hoti hai:
    - step_number iteration order track karta hai
    - step_type identify karta hai yeh konsa phase hai
    - thought/observation/reflection optional hain (sirbhi har step mein nahi hote)
    - timestamp + step_number together unique record banate hain

    Example:
        >>> step = AgentStep(
        ...     step_number=1,
        ...     step_type=StepType.THINK,
        ...     thought="User ke code mein security issues check karne chahiye"
        ... )
        >>> step.step_type
        <StepType.THINK: 'think'>
    """
    step_number: int                             # Kaunsa iteration hai (1, 2, 3...)
    step_type: StepType                          # THINK, ACT, OBSERVE, ya REFLECT
    thought: str | None = None                   # LLM ka reasoning text (THINK step pe)
    action: ToolCall | None = None                # Tool call decision (ACT step pe)
    observation: ToolResult | None = None         # Tool ka result (OBSERVE step pe)
    reflection: str | None = None                # LLM ka evaluation (REFLECT step pe)
    timestamp: datetime = field(default_factory=_utcnow)  # Kab yeh step complete hua

    def __repr__(self) -> str:
        """Compact debug representation - long text truncate karte hain."""
        parts = [f"#{self.step_number}", f"type={self.step_type.value}"]
        if self.thought:
            parts.append(f"thought={self.thought[:30]!r}...")
        if self.action:
            parts.append(f"action={self.action.tool_name}")
        if self.observation:
            status = "OK" if self.observation.success else "FAIL"
            parts.append(f"obs={status}")
        if self.reflection:
            parts.append(f"reflect={self.reflection[:30]!r}...")
        return f"AgentStep({', '.join(parts)})"

    @property
    def is_terminal(self) -> bool:
        """
        Check karo ke yeh step final answer deliver karta hai ya nahi.
        ACT step with no tool_call matlab LLM ne direct answer diya.
        """
        return (
            self.step_type == StepType.ACT
            and self.action is None
            and self.thought is not None
        )


# =============================================================================
# DATACLASSES - User request / Final result
# =============================================================================
@dataclass
class ReviewRequest:
    """
    User ke code review request ko represent karta hai.
    User ya to GitHub URL de sakta hai ya direct code paste kar sakta hai.

    Yeh dataclass API layer ke through aata hai aur agent ko
    batati hai ke exactly kya review karna hai.

    Fields:
    - github_url: Agar user ne repo URL diya (optional)
    - code_content: Agar user ne direct code diya (optional)
    - analysis_type: "full", "security", "performance", "style" etc.
    - request_time: Kab request aayi (audit log ke liye)
    - request_id: Unique ID har request ke liye (correlation ke liye)

    Example:
        >>> req = ReviewRequest(
        ...     github_url="https://github.com/user/repo",
        ...     analysis_type="security"
        ... )
        >>> req.analysis_type
        'security'
    """
    github_url: str | None = None                # GitHub repo URL (alternative to code_content)
    code_content: str | None = None              # Direct code paste (alternative to github_url)
    analysis_type: str = "full"                  # Analysis type: full, security, performance, style
    request_time: datetime | None = None         # Request arrival time
    request_id: str = field(default_factory=lambda: str(uuid.uuid4()))  # Unique request ID

    def __post_init__(self) -> None:
        """
        Post-init validation:
        - request_time default set karo agar None ho
        - Ensure at least one source (URL ya code) provided ho
        """
        if self.request_time is None:
            self.request_time = _utcnow()

    def __repr__(self) -> str:
        """Debug representation - dono optional fields dikhata hai."""
        return (
            f"ReviewRequest(github_url={self.github_url!r}, "
            f"code_len={len(self.code_content) if self.code_content else 0}, "
            f"type={self.analysis_type!r})"
        )

    def has_source(self) -> bool:
        """Check karo ke request valid hai - kam az kam ek source hona chahiye."""
        return bool(self.github_url) or bool(self.code_content)


@dataclass
class ReviewResult:
    """
    Agent ka final output - user ko return hone wala result.
    API response yahi shape use karega.

    Yeh dataclass front-end aur API ke liye contract define karti hai:
    - success: Overall operation kamyab hua ya nahi
    - quality_score: 0-10 mein code quality rating
    - issues: List of found issues (har ek dict with severity, line, etc.)
    - report: Human-readable detailed report (markdown format mein)
    - steps_taken: Kitne ReACT iterations lagay
    - execution_time: Total time seconds mein
    - errors: List of non-fatal errors (e.g., ek tool fail hua par baqi kaam hua)

    Example:
        >>> result = ReviewResult(
        ...     success=True,
        ...     quality_score=7.5,
        ...     issues=[{"severity": "medium", "line": 42, "msg": "..."}],
        ...     report="# Code Review\\n\\nFound 1 issue...",
        ...     steps_taken=3,
        ...     execution_time=12.4
        ... )
        >>> result.quality_score
        7.5
    """
    success: bool                                # Operation overall success ya failure
    quality_score: float                         # 0-10 scale pe code quality rating
    issues: list[dict[str, Any]] = field(default_factory=list)  # Found issues list
    report: str = ""                             # Human-readable report (markdown supported)
    steps_taken: int = 0                         # Kitne ReACT iterations execute hue
    execution_time: float = 0.0                  # Total processing time (seconds)
    errors: list[str] | None = None              # Non-fatal errors jo collect hue
    timestamp: datetime = field(default_factory=_utcnow)  # Kab result generate hua

    def __repr__(self) -> str:
        """Compact success representation - key metrics dikhata hai."""
        return (
            f"ReviewResult(success={self.success}, "
            f"score={self.quality_score:.2f}, "
            f"issues={len(self.issues)}, steps={self.steps_taken})"
        )

    def to_dict(self) -> dict[str, Any]:
        """
        API response ke liye dict conversion.
        Frontend/Postman/etc easily consume kar sakein.
        """
        return {
            "success": self.success,
            "quality_score": self.quality_score,
            "issues": self.issues,
            "report": self.report,
            "steps_taken": self.steps_taken,
            "execution_time": self.execution_time,
            "errors": self.errors or [],
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
        }
