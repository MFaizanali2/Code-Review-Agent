import ast
import subprocess
import json
import re
from .base_tool import BaseTool

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

    def __init__(self):
        super().__init__(
            name="check_security",
            description="Python file mein security vulnerabilities scan karo"
        )

    async def execute(self, code_path: str) -> dict:
        vulnerabilities = []

        try:
            with open(code_path, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()

            for line_num, line in enumerate(lines, 1):
                for check in self.DANGEROUS_PATTERNS:
                    if re.search(check["pattern"], line, re.IGNORECASE):
                        vulnerabilities.append({
                            "line": line_num,
                            "issue": check["issue"],
                            "severity": check["severity"],
                            "code": line.strip()
                        })
        except Exception as e:
            return {"status": "error", "message": f"File read error: {str(e)}"}

        bandit_results = {}
        try:
            result = subprocess.run(
                ["bandit", "-r", code_path, "-f", "json", "-q"],
                capture_output=True, text=True, timeout=30
            )
            if result.stdout:
                bandit_results = json.loads(result.stdout)
        except (subprocess.TimeoutExpired, FileNotFoundError, json.JSONDecodeError):
            bandit_results = {"note": "Bandit not available or timed out"}

        total = len(vulnerabilities)
        risk_level = (
            "CRITICAL" if any(v["severity"] == "CRITICAL" for v in vulnerabilities)
            else "HIGH" if any(v["severity"] == "HIGH" for v in vulnerabilities)
            else "MEDIUM" if total > 0
            else "SAFE"
        )

        return {
            "status": "success",
            "vulnerabilities": vulnerabilities,
            "bandit_results": bandit_results,
            "total_issues": total,
            "risk_level": risk_level
        }
