"""
API Client — CodeSense AI
Handles all communication with the FastAPI backend.
Falls back to mock data if backend is offline (Demo Mode).
"""

import requests
import logging
from datetime import datetime
from typing import Optional
import random

logger = logging.getLogger(__name__)


class APIClient:
    def __init__(self, endpoint: str) -> None:
        self.endpoint = endpoint.rstrip("/")
        self.timeout = 120

    # ─── Health Check ────────────────────────────────────────────────────────
    def health_check(self) -> bool:
        """Ping the backend to check if it's alive."""
        try:
            response = requests.get(
                f"{self.endpoint}/health",
                timeout=5
            )
            return response.status_code == 200
        except Exception as e:
            logger.warning(f"Health check failed: {e}")
            return False

    # ─── Main Review Call ─────────────────────────────────────────────────────
    def review_code(
        self,
        github_url: Optional[str] = None,
        code_content: Optional[str] = None,
        model: str = "gemini-2.0-flash",
        depth: str = "Standard"
    ) -> Optional[dict]:
        """
        Send code/repo to backend for AI review.
        Returns structured result or None on failure.
        """
        payload = {
            "model": model,
            "depth": depth
        }
        if github_url:
            payload["github_url"] = github_url
        if code_content:
            payload["code_content"] = code_content

        try:
            response = requests.post(
                f"{self.endpoint}/api/review",
                json=payload,
                timeout=self.timeout
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.ConnectionError:
            logger.warning("Backend offline — demo mode active")
            return None
        except requests.exceptions.Timeout:
            logger.error("Request timed out after 120s")
            return {"status": "error", "message": "Request timed out. Try again."}
        except requests.exceptions.HTTPError as e:
            logger.error(f"HTTP Error: {e}")
            return {"status": "error", "message": str(e)}
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            return None

    # ─── History ──────────────────────────────────────────────────────────────
    def get_history(self, limit: int = 20) -> list:
        """Fetch review history from backend database."""
        try:
            response = requests.get(
                f"{self.endpoint}/api/reviews/history",
                params={"limit": limit},
                timeout=10
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.warning(f"Could not fetch history: {e}")
            return []

    # ─── Mock Data (Demo Mode) ────────────────────────────────────────────────
    def get_mock_result(self, payload: dict) -> dict:
        """
        Generate realistic mock data when backend is offline.
        Used for demos, presentations, and development.
        """
        score = random.randint(55, 92)
        source = payload.get("github_url", "Pasted Code")

        return {
            "status": "success",
            "demo_mode": True,
            "overall_score": score,
            "files_analyzed": random.randint(8, 25),
            "lines_of_code": random.randint(500, 3000),
            "critical_issues": random.randint(1, 5),
            "warnings": random.randint(3, 12),
            "source": source,
            "security_issues": [
                {
                    "title": "SQL Injection Risk Detected",
                    "severity": "critical",
                    "line": f"Line {random.randint(20, 100)}",
                    "desc": "User input directly used in SQL query. Sanitize all inputs or use parameterized queries."
                },
                {
                    "title": "Hardcoded Secret Key Found",
                    "severity": "critical",
                    "line": f"Line {random.randint(5, 20)}",
                    "desc": "API credentials found in source code. Move to .env file and add to .gitignore."
                },
                {
                    "title": "Insecure Random Number Generation",
                    "severity": "warning",
                    "line": f"Line {random.randint(50, 150)}",
                    "desc": "random.random() used for security token. Use secrets.token_hex() instead."
                },
                {
                    "title": "No Rate Limiting on Auth Endpoints",
                    "severity": "warning",
                    "line": "Routes: /login, /register",
                    "desc": "Authentication endpoints are vulnerable to brute force attacks."
                },
                {
                    "title": "All Dependencies Scanned — Clean",
                    "severity": "good",
                    "line": "requirements.txt",
                    "desc": "No known CVEs found in current dependency versions."
                }
            ],
            "performance_issues": [
                {
                    "title": "N+1 Database Query Pattern",
                    "severity": "critical",
                    "line": f"Lines {random.randint(100, 200)}-{random.randint(201, 250)}",
                    "desc": "Querying database inside a loop causes exponential performance degradation."
                },
                {
                    "title": "Blocking Sync Call in Async Context",
                    "severity": "warning",
                    "line": f"Line {random.randint(80, 180)}",
                    "desc": "requests.get() blocks event loop. Use httpx or aiohttp for async HTTP calls."
                },
                {
                    "title": "Large Object in Memory",
                    "severity": "warning",
                    "line": f"Line {random.randint(150, 300)}",
                    "desc": "Entire dataset loaded into memory. Use pagination or streaming instead."
                },
                {
                    "title": "Proper Use of List Comprehensions",
                    "severity": "good",
                    "line": "Multiple locations",
                    "desc": "Pythonic and efficient use of comprehensions throughout the codebase."
                }
            ],
            "quality_metrics": {
                "maintainability": random.randint(55, 90),
                "readability": random.randint(50, 85),
                "test_coverage": random.randint(20, 70),
                "documentation": random.randint(30, 80),
                "complexity": random.randint(50, 90),
                "modularity": random.randint(60, 95)
            },
            "suggestions": [
                "Add type hints to all function signatures for better IDE support and readability",
                "Write unit tests to bring coverage above 80% — especially for core business logic",
                "Add docstrings to public classes and functions following Google or NumPy style",
                "Break down functions exceeding 50 lines into smaller, single-responsibility units",
                "Add input validation layer using Pydantic models at API boundaries",
                "Consider adding pre-commit hooks to enforce code style automatically"
            ],
            "full_report": self._generate_full_report(score, source)
        }

    def _generate_full_report(self, score: int, source: str) -> str:
        """Generate a formatted markdown report."""
        grade = "A" if score >= 90 else "B" if score >= 75 else "C" if score >= 60 else "D"

        return f"""## 🧠 CodeSense AI — Automated Code Review Report

**Source:** `{source}`
**Generated:** {datetime.now().strftime('%B %d, %Y at %H:%M')}
**Powered by:** Gemini 2.0 Flash via ReACT Agent

---

## Overall Score: {score}/100 (Grade: {grade})

{'✅ Your codebase is in good shape with minor improvements needed.' if score >= 75 else '⚠️ Your codebase needs attention in several areas before production.' if score >= 60 else '❌ Critical issues found. Immediate action required.'}

---

## 🛡️ Security Summary

Critical security vulnerabilities were detected that could expose the application to attacks.
The most urgent issues involve improper input sanitization and exposed credentials.

**Immediate Actions:**
1. Fix SQL injection vulnerability using parameterized queries
2. Move all secrets to environment variables (`.env` file)
3. Implement rate limiting on authentication endpoints

---

## ⚡ Performance Summary

Performance bottlenecks identified that could cause degradation under load.
The N+1 query pattern is the highest priority fix.

**Recommended Optimizations:**
1. Batch database queries outside loops
2. Replace blocking HTTP calls with async equivalents
3. Implement pagination for large dataset endpoints

---

## 🏗️ Code Quality Summary

The code demonstrates solid fundamentals with room for improvement in
documentation, testing, and maintainability practices.

**Best Practices to Adopt:**
- Add comprehensive type hints
- Increase test coverage to 80%+
- Add docstrings to all public APIs
- Enable pre-commit hooks for style enforcement

---

*Generated by CodeSense AI · Agentic AI Course Project · 2025*
"""