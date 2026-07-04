import ast
import json
import re
import subprocess
from agent.tools.base import BaseTool, ToolResult, ToolSchema


class SecurityCheckerTool(BaseTool):

    DANGEROUS_PATTERNS = [
        {"pattern": r"\beval\s*\(", "issue": "eval() usage — code injection risk", "severity": "CRITICAL"},
        {"pattern": r"\bexec\s*\(", "issue": "exec() usage — arbitrary code execution", "severity": "CRITICAL"},
        {"pattern": r"os\.system\s*\(", "issue": "os.system() — shell injection risk", "severity": "HIGH"},
        {"pattern": r"subprocess\.call\s*\(.*shell\s*=\s*True", "issue": "subprocess with shell=True", "severity": "HIGH"},
        {"pattern": r"pickle\.loads?\s*\(", "issue": "pickle usage — unsafe deserialization", "severity": "HIGH"},
        {"pattern": r"password\s*=\s*['\"]", "issue": "Hardcoded password detected", "severity": "HIGH"},
        {"pattern": r"secret\s*=\s*['\"]", "issue": "Hardcoded secret detected", "severity": "HIGH"},
        {"pattern": r"api_key\s*=\s*['\"]", "issue": "Hardcoded API key detected", "severity": "HIGH"},
        {"pattern": r"SELECT.+WHERE.+\+", "issue": "Possible SQL injection via string concat", "severity": "CRITICAL"},
        {"pattern": r"__import__\s*\(", "issue": "Dynamic import — potential code injection", "severity": "MEDIUM"},
    ]

    @property
    def name(self) -> str:
        return "check_security"

    @property
    def description(self) -> str:
        return "Scan a Python file for security vulnerabilities"

    async def run(self, tool_input: dict) -> ToolResult:
        code_path = tool_input.get("code_path", "")
        if not code_path:
            return ToolResult(success=False, data={}, error="code_path is required")

        vulnerabilities = []

        try:
            with open(code_path, "r", encoding="utf-8", errors="ignore") as f:
                lines = f.readlines()

            for line_num, line in enumerate(lines, 1):
                for check in self.DANGEROUS_PATTERNS:
                    if re.search(check["pattern"], line, re.IGNORECASE):
                        vulnerabilities.append({
                            "line": line_num,
                            "issue": check["issue"],
                            "severity": check["severity"],
                            "code": line.strip(),
                        })
        except Exception as e:
            return ToolResult(success=False, data={}, error=f"File read error: {str(e)}")

        bandit_results = {}
        try:
            result = subprocess.run(
                ["bandit", "-r", code_path, "-f", "json", "-q"],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.stdout:
                bandit_results = json.loads(result.stdout)
        except (subprocess.TimeoutExpired, FileNotFoundError, json.JSONDecodeError):
            bandit_results = {"note": "Bandit not available or timed out"}

        total = len(vulnerabilities)
        risk_level = (
            "CRITICAL"
            if any(v["severity"] == "CRITICAL" for v in vulnerabilities)
            else "HIGH"
            if any(v["severity"] == "HIGH" for v in vulnerabilities)
            else "MEDIUM"
            if total > 0
            else "SAFE"
        )

        return ToolResult(
            success=True,
            data={
                "status": "success",
                "vulnerabilities": vulnerabilities,
                "bandit_results": bandit_results,
                "total_issues": total,
                "risk_level": risk_level,
            },
        )

    def schema(self) -> ToolSchema:
        return ToolSchema(
            name=self.name,
            description=self.description,
            parameters={
                "code_path": {
                    "type": "string",
                    "description": "Path to the Python file to scan",
                },
            },
            required=["code_path"],
        )
