"""
constants.py - Agent module ki saari constants yahan centralized hain.
Ek jagah se poori configuration control hoti hai - production mein
.env ya config file se override kar sakte hain, lekin defaults yahan hain.

Rule: Magic numbers/strings code mein nahi honi chahiye - sab yahan.
Modify karne ke liye sirf yeh file edit karna kaafi hai.
"""


# =============================================================================
# AGENT STATES - workflow ke possible states
# =============================================================================
# Yeh states agent ki lifecycle dikhate hain.
# State machine ke through transition hote hain: IDLE -> THINKING -> ... -> COMPLETED/FAILED
AGENT_STATES: dict[str, str] = {
    "IDLE":       "Agent waiting for request",            # Koi request nahi, input ka intezaar
    "THINKING":   "Agent reasoning about next step",       # LLM soch raha hai kya karna hai
    "EXECUTING":  "Agent running a tool",                 # Tool call execute ho raha hai
    "OBSERVING":  "Agent analyzing tool results",         # Tool ka result evaluate ho raha hai
    "REFLECTING": "Agent evaluating its own progress",    # Khud par evaluate kar raha hai
    "COMPLETED":  "Task completed successfully",          # Kaam ho gaya, final answer ready
    "FAILED":     "Task failed, no answer produced",      # Tool errors ya logic failure
    "ERROR":      "System error occurred",                # Unexpected exception/crash
}


# =============================================================================
# TOOLS - available tools ke identifiers
# =============================================================================
# Yeh keys tool registry mein use hoti hain.
# Person 2 apne tools in identifiers ke against register karega.
# Key = constant name (uppercase), Value = actual tool identifier (snake_case)
TOOLS: dict[str, str] = {
    "FETCH_REPO":        "fetch_repository",         # GitHub se code fetch karta hai
    "ANALYZE_CODE":      "analyze_code",             # General code analysis
    "SECURITY_AUDIT":    "security_audit",           # Security vulnerabilities check
    "PERFORMANCE_CHECK": "performance_check",        # Performance bottlenecks dhundna
    "GENERATE_REPORT":   "generate_report",          # Final markdown report banana
}


# =============================================================================
# STEP TYPES - ReACT cycle ke phases
# =============================================================================
# Yeh list validation aur logging ke liye use hoti hai.
# agent_types.StepType enum ke saath sync mein rakhna chahiye.
STEP_TYPES: list[str] = ["THINK", "ACT", "OBSERVE", "REFLECT"]


# =============================================================================
# EXECUTION LIMITS - loops aur timeouts
# =============================================================================
# Production safety ke liye hard limits - isse zyada pe task abort ho jata hai.

MAX_STEPS: int = 10
# ReACT loop ki maximum iterations. Zyada = expensive, kam = kaam adhura.
# Test results: 5-7 steps average, 10 safe upper bound.

TOOL_TIMEOUT: int = 120
# Har tool call ka max time (seconds). Isse zyada laga to tool cancel.
# 120s = 2 min - Pylint/Bandit jaise tools ke liye sufficient.

RETRY_ATTEMPTS: int = 2
# Failed tools kitni baar retry honi chahiyein. 0 = no retry, 2 = original + 2 retries.
# Transient errors (network) ke liye helpful.

MEMORY_MAX_SIZE: int = 100
# Memory mein maximum steps store honge. Isse zyada pe oldest trim.
# Long sessions mein memory leak se bachata hai.


# =============================================================================
# CONFIGURATION - agent-wide settings
# =============================================================================
# Yeh values runtime pe tune ki ja sakti hain.

LOG_LEVEL: str = "INFO"
# Logging level: DEBUG, INFO, WARNING, ERROR, CRITICAL.
# Production mein INFO ya WARNING rakhein, dev mein DEBUG.

DEFAULT_ANALYSIS_TYPE: str = "full"
# Agar user ne specify nahi kiya to yeh type use hoga.
# Options: "full", "security", "performance", "style"

VERSION: str = "1.0.0"
# Agent version - API responses mein bhejte hain debugging ke liye.
# Semantic versioning follow karo: MAJOR.MINOR.PATCH.
