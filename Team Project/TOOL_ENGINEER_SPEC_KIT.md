# 🔧 Tool Engineer — Spec Kit
## Project: AI-Powered Code Review Agent
**Role:** Person 2 — Tool Engineer  
**Stack:** Python, FastAPI, AST, Bandit, Pylint, GitPython  
**Scope:** Build all tools that the Agent (Person 1) will call during ReACT loop execution

---

## 📁 Folder Structure to Create

```
tools/
├── __init__.py
├── base_tool.py
├── github_tool.py
├── code_analyzer.py
├── security_checker.py
├── performance_checker.py
├── report_generator.py
└── utils.py

tests/
└── test_tools.py
```

---

## 📦 Dependencies (requirements.txt entries)

```
gitpython==3.1.41
bandit==1.7.8
pylint==3.2.0
radon==6.0.1
aiofiles==23.2.1
```

---

## ✅ FILE 1: `tools/base_tool.py`

**Purpose:** Abstract base class. Every tool MUST inherit from this.

```python
from abc import ABC, abstractmethod
from typing import Any, Dict

class BaseTool(ABC):
    def __init__(self, name: str, description: str):
        self.name = name
        self.description = description

    @abstractmethod
    async def execute(self, **kwargs) -> Dict[str, Any]:
        """
        Tool ka main logic yahan likho.
        Always return dict with 'status': 'success' | 'error'
        """
        pass

    def to_schema(self) -> Dict[str, str]:
        """
        Agent (Person 1) ke liye tool ka schema.
        LLM is schema ko read karke decide karta hai konsa tool call karna hai.
        """
        return {
            "name": self.name,
            "description": self.description
        }
```

**Rules:**
- Har tool `BaseTool` ko inherit ZAROOR karega
- `execute()` method har tool mein implement HONA CHAHIYE
- Return type hamesha `Dict[str, Any]` hoga
- Return dict mein `"status": "success"` ya `"status": "error"` zaroor hoga

---

## ✅ FILE 2: `tools/github_tool.py`

**Purpose:** GitHub URL se repository clone karna aur files ki list return karna.

```python
import os
import shutil
from git import Repo, GitCommandError
from .base_tool import BaseTool

class GitHubTool(BaseTool):
    def __init__(self):
        super().__init__(
            name="fetch_repository",
            description="GitHub repository clone karo aur files list karo"
        )

    async def execute(self, github_url: str, target_dir: str = "./temp_repo") -> dict:
        """
        Args:
            github_url (str): GitHub repo URL e.g. https://github.com/user/repo
            target_dir (str): Local path jahan clone hoga

        Returns:
            dict: {
                status, repo_path, file_count,
                languages, files, python_files
            }
        """
        try:
            # Agar folder pehle se exist kare to delete karo
            if os.path.exists(target_dir):
                shutil.rmtree(target_dir)

            repo = Repo.clone_from(github_url, target_dir)
            all_files = self._get_all_files(target_dir)
            python_files = [f for f in all_files if f.endswith(".py")]
            languages = self._detect_languages(target_dir)

            return {
                "status": "success",
                "repo_path": target_dir,
                "file_count": len(all_files),
                "python_file_count": len(python_files),
                "languages": languages,
                "files": all_files,
                "python_files": python_files
            }

        except GitCommandError as e:
            return {"status": "error", "message": f"Git error: {str(e)}"}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def _get_all_files(self, path: str) -> list:
        """Recursively sab files collect karo"""
        files = []
        for root, dirs, filenames in os.walk(path):
            # .git folder skip karo
            dirs[:] = [d for d in dirs if d != '.git']
            for file in filenames:
                files.append(os.path.join(root, file))
        return files

    def _detect_languages(self, path: str) -> dict:
        """File extensions count karo"""
        extensions = {}
        for root, dirs, files in os.walk(path):
            dirs[:] = [d for d in dirs if d != '.git']
            for file in files:
                ext = os.path.splitext(file)[1].lower()
                if ext:
                    extensions[ext] = extensions.get(ext, 0) + 1
        return extensions
```

**Inputs:**
| Parameter | Type | Required | Default |
|-----------|------|----------|---------|
| `github_url` | str | YES | — |
| `target_dir` | str | NO | `./temp_repo` |

**Output keys:** `status`, `repo_path`, `file_count`, `python_file_count`, `languages`, `files`, `python_files`

---

## ✅ FILE 3: `tools/code_analyzer.py`

**Purpose:** Python files ka AST (Abstract Syntax Tree) parse karke structure nikalna.

```python
import ast
import os
from .base_tool import BaseTool

class CodeAnalyzerTool(BaseTool):
    def __init__(self):
        super().__init__(
            name="analyze_code_structure",
            description="Python file ka structure analyze karo — functions, classes, imports, complexity"
        )

    async def execute(self, code_path: str) -> dict:
        """
        Args:
            code_path (str): Python file ka path

        Returns:
            dict: {
                status, data: {
                    functions, classes, imports,
                    lines_of_code, complexity, has_docstrings
                }
            }
        """
        try:
            with open(code_path, 'r', encoding='utf-8', errors='ignore') as f:
                code = f.read()

            tree = ast.parse(code)

            analysis = {
                "file": code_path,
                "functions": [],
                "classes": [],
                "imports": [],
                "lines_of_code": len(code.splitlines()),
                "complexity": self._calculate_complexity(tree),
                "has_docstrings": False
            }

            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    has_doc = (
                        isinstance(node.body[0], ast.Expr)
                        and isinstance(node.body[0].value, ast.Constant)
                        if node.body else False
                    )
                    analysis["functions"].append({
                        "name": node.name,
                        "line": node.lineno,
                        "args_count": len(node.args.args),
                        "has_docstring": has_doc
                    })

                elif isinstance(node, ast.ClassDef):
                    analysis["classes"].append({
                        "name": node.name,
                        "line": node.lineno,
                        "method_count": len([
                            n for n in node.body if isinstance(n, ast.FunctionDef)
                        ])
                    })

                elif isinstance(node, (ast.Import, ast.ImportFrom)):
                    analysis["imports"].append(ast.unparse(node))

            # Check if module has top-level docstring
            if (tree.body and isinstance(tree.body[0], ast.Expr)
                    and isinstance(tree.body[0].value, ast.Constant)):
                analysis["has_docstrings"] = True

            return {"status": "success", "data": analysis}

        except SyntaxError as e:
            return {"status": "error", "message": f"Syntax error in file: {str(e)}"}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def _calculate_complexity(self, tree: ast.AST) -> int:
        """
        Cyclomatic complexity calculate karo.
        Har branch (if/for/while/except) +1 complexity add karta hai.
        Score > 10 = complex code
        """
        complexity = 1
        for node in ast.walk(tree):
            if isinstance(node, (
                ast.If, ast.While, ast.For,
                ast.ExceptHandler, ast.With,
                ast.Assert, ast.comprehension
            )):
                complexity += 1
        return complexity
```

**Inputs:**
| Parameter | Type | Required |
|-----------|------|----------|
| `code_path` | str | YES |

**Output keys:** `status`, `data.file`, `data.functions[]`, `data.classes[]`, `data.imports[]`, `data.lines_of_code`, `data.complexity`, `data.has_docstrings`

**Complexity Scale:**
- `1–5` = Simple ✅
- `6–10` = Moderate ⚠️
- `10+` = Complex 🔴

---

## ✅ FILE 4: `tools/security_checker.py`

**Purpose:** Python files mein common security vulnerabilities dhundna using pattern matching + Bandit.

```python
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
        """
        Args:
            code_path (str): Python file ya directory ka path

        Returns:
            dict: {
                status,
                vulnerabilities: [ {line, issue, severity, code} ],
                bandit_results: {...},
                total_issues: int,
                risk_level: str
            }
        """
        vulnerabilities = []

        # Method 1: Manual regex pattern scan
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

        # Method 2: Bandit tool (professional scanner)
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
```

**Inputs:**
| Parameter | Type | Required |
|-----------|------|----------|
| `code_path` | str | YES |

**Severity Levels:** `CRITICAL` → `HIGH` → `MEDIUM` → `SAFE`

**Output keys:** `status`, `vulnerabilities[]`, `bandit_results`, `total_issues`, `risk_level`

---

## ✅ FILE 5: `tools/performance_checker.py`

**Purpose:** Python code mein performance anti-patterns dhundna using AST analysis.

```python
import ast
from .base_tool import BaseTool

class PerformanceCheckerTool(BaseTool):
    def __init__(self):
        super().__init__(
            name="check_performance",
            description="Python code mein performance issues detect karo"
        )

    async def execute(self, code_path: str) -> dict:
        """
        Args:
            code_path (str): Python file ka path

        Returns:
            dict: {
                status,
                issues: [ {line, issue, suggestion, severity} ],
                total_issues: int,
                performance_score: int  # 0-100
            }
        """
        issues = []

        try:
            with open(code_path, 'r', encoding='utf-8', errors='ignore') as f:
                code = f.read()

            tree = ast.parse(code)

            # Check 1: Nested loops (O(n²) complexity)
            self._check_nested_loops(tree, issues)

            # Check 2: List append inside loop
            self._check_loop_appends(tree, issues)

            # Check 3: Global variable usage in loops
            self._check_global_in_loop(tree, issues)

            # Check 4: Repeated function calls in loop condition
            self._check_len_in_loop(tree, issues)

        except SyntaxError as e:
            return {"status": "error", "message": f"Syntax error: {str(e)}"}
        except Exception as e:
            return {"status": "error", "message": str(e)}

        score = max(0, 100 - (len(issues) * 10))

        return {
            "status": "success",
            "issues": issues,
            "total_issues": len(issues),
            "performance_score": score
        }

    def _check_nested_loops(self, tree, issues):
        for node in ast.walk(tree):
            if isinstance(node, (ast.For, ast.While)):
                for child in ast.walk(node):
                    if isinstance(child, (ast.For, ast.While)) and child is not node:
                        issues.append({
                            "line": node.lineno,
                            "issue": "Nested loop detected — O(n²) time complexity",
                            "suggestion": "Use dict/set lookup or vectorized operations",
                            "severity": "MEDIUM"
                        })
                        break  # Ek hi issue per loop report karo

    def _check_loop_appends(self, tree, issues):
        for node in ast.walk(tree):
            if isinstance(node, (ast.For, ast.While)):
                for child in ast.walk(node):
                    if (isinstance(child, ast.Call)
                            and hasattr(child.func, 'attr')
                            and child.func.attr == 'append'):
                        issues.append({
                            "line": node.lineno,
                            "issue": "list.append() inside loop",
                            "suggestion": "Use list comprehension instead: [x for x in ...]",
                            "severity": "LOW"
                        })
                        break

    def _check_global_in_loop(self, tree, issues):
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                global_names = {g.names[0] for g in ast.walk(node)
                                if isinstance(g, ast.Global)}
                for child in ast.walk(node):
                    if isinstance(child, (ast.For, ast.While)):
                        for subchild in ast.walk(child):
                            if (isinstance(subchild, ast.Name)
                                    and subchild.id in global_names):
                                issues.append({
                                    "line": child.lineno,
                                    "issue": f"Global variable '{subchild.id}' accessed in loop",
                                    "suggestion": "Cache global in local variable before loop",
                                    "severity": "LOW"
                                })
                                break

    def _check_len_in_loop(self, tree, issues):
        for node in ast.walk(tree):
            if isinstance(node, ast.While):
                for child in ast.walk(node.test):
                    if (isinstance(child, ast.Call)
                            and isinstance(child.func, ast.Name)
                            and child.func.id == 'len'):
                        issues.append({
                            "line": node.lineno,
                            "issue": "len() called in while condition repeatedly",
                            "suggestion": "Store len() result in variable before loop",
                            "severity": "LOW"
                        })
```

**Output keys:** `status`, `issues[]`, `total_issues`, `performance_score`

**Performance Score:** `100` = No issues, `-10` per issue found

---

## ✅ FILE 6: `tools/report_generator.py`

**Purpose:** Sab tools ke results ko combine karke ek final JSON report banana.

```python
from datetime import datetime
from .base_tool import BaseTool

class ReportGeneratorTool(BaseTool):
    def __init__(self):
        super().__init__(
            name="generate_report",
            description="Sab analysis results ko combine karke final review report banao"
        )

    async def execute(self, analysis_data: dict) -> dict:
        """
        Args:
            analysis_data (dict): All tool results combined:
                {
                    github: GitHubTool result,
                    code: CodeAnalyzerTool result,
                    security: SecurityCheckerTool result,
                    performance: PerformanceCheckerTool result
                }

        Returns:
            dict: {
                status,
                report: {
                    meta, summary, scores,
                    issues, recommendations, final_verdict
                }
            }
        """
        try:
            github   = analysis_data.get("github", {})
            code     = analysis_data.get("code", {}).get("data", {})
            security = analysis_data.get("security", {})
            perf     = analysis_data.get("performance", {})

            security_score   = max(0, 100 - (security.get("total_issues", 0) * 15))
            performance_score = perf.get("performance_score", 100)
            quality_score    = self._calculate_quality_score(code)
            overall_score    = round(
                (security_score * 0.4) + (performance_score * 0.3) + (quality_score * 0.3)
            )

            report = {
                "meta": {
                    "generated_at": datetime.now().isoformat(),
                    "repo_files": github.get("file_count", 0),
                    "python_files": github.get("python_file_count", 0),
                    "languages": github.get("languages", {})
                },
                "summary": {
                    "total_functions": len(code.get("functions", [])),
                    "total_classes": len(code.get("classes", [])),
                    "lines_of_code": code.get("lines_of_code", 0),
                    "cyclomatic_complexity": code.get("complexity", 0),
                    "security_issues": security.get("total_issues", 0),
                    "performance_issues": perf.get("total_issues", 0),
                    "risk_level": security.get("risk_level", "UNKNOWN")
                },
                "scores": {
                    "security":    security_score,
                    "performance": performance_score,
                    "quality":     quality_score,
                    "overall":     overall_score
                },
                "issues": {
                    "security":    security.get("vulnerabilities", []),
                    "performance": perf.get("issues", [])
                },
                "recommendations": self._build_recommendations(
                    security, perf, code
                ),
                "final_verdict": self._get_verdict(overall_score)
            }

            return {"status": "success", "report": report}

        except Exception as e:
            return {"status": "error", "message": str(e)}

    def _calculate_quality_score(self, code: dict) -> int:
        score = 100
        complexity = code.get("complexity", 0)
        if complexity > 10:
            score -= 30
        elif complexity > 5:
            score -= 10
        if not code.get("has_docstrings", False):
            score -= 20
        return max(0, score)

    def _build_recommendations(self, security, perf, code) -> list:
        recs = []
        if security.get("total_issues", 0) > 0:
            recs.append({
                "priority": "HIGH",
                "message": f"Fix {security['total_issues']} security issue(s) immediately",
                "category": "Security"
            })
        if perf.get("total_issues", 0) > 0:
            recs.append({
                "priority": "MEDIUM",
                "message": "Refactor nested loops and use list comprehensions",
                "category": "Performance"
            })
        if not code.get("has_docstrings", False):
            recs.append({
                "priority": "LOW",
                "message": "Add docstrings to functions and modules",
                "category": "Documentation"
            })
        if code.get("complexity", 0) > 10:
            recs.append({
                "priority": "MEDIUM",
                "message": "Reduce cyclomatic complexity — break large functions into smaller ones",
                "category": "Maintainability"
            })
        return recs

    def _get_verdict(self, score: int) -> str:
        if score >= 80:
            return "✅ GOOD — Code is production-ready with minor improvements"
        elif score >= 60:
            return "⚠️ FAIR — Several issues need attention before deployment"
        else:
            return "🔴 POOR — Critical issues must be fixed before deployment"
```

**Output keys:** `status`, `report.meta`, `report.summary`, `report.scores`, `report.issues`, `report.recommendations`, `report.final_verdict`

---

## ✅ FILE 7: `tools/utils.py`

**Purpose:** Shared helper functions jo multiple tools use karengi.

```python
import os
import shutil
from typing import List

def cleanup_temp_dir(path: str) -> None:
    """Clone ki hui temp directory delete karo"""
    if os.path.exists(path):
        shutil.rmtree(path)

def get_python_files(directory: str) -> List[str]:
    """Recursively sab .py files return karo"""
    py_files = []
    for root, dirs, files in os.walk(directory):
        dirs[:] = [d for d in dirs if d not in ['.git', '__pycache__', '.venv']]
        for file in files:
            if file.endswith('.py'):
                py_files.append(os.path.join(root, file))
    return py_files

def is_valid_github_url(url: str) -> bool:
    """Check karo URL valid GitHub URL hai ya nahi"""
    return url.startswith("https://github.com/") and len(url.split("/")) >= 5

def safe_read_file(path: str) -> str:
    """File safely read karo — encoding errors ignore karo"""
    try:
        with open(path, 'r', encoding='utf-8', errors='ignore') as f:
            return f.read()
    except Exception:
        return ""

def severity_rank(severity: str) -> int:
    """Severity ko sort karne ke liye numeric rank do"""
    return {"CRITICAL": 4, "HIGH": 3, "MEDIUM": 2, "LOW": 1, "SAFE": 0}.get(severity, 0)
```

---

## ✅ FILE 8: `tools/__init__.py`

**Purpose:** Sab tools ek jagah export karo taake agent easily import kar sake.

```python
from .github_tool import GitHubTool
from .code_analyzer import CodeAnalyzerTool
from .security_checker import SecurityCheckerTool
from .performance_checker import PerformanceCheckerTool
from .report_generator import ReportGeneratorTool

# Agent (Person 1) yeh list use karega
ALL_TOOLS = [
    GitHubTool(),
    CodeAnalyzerTool(),
    SecurityCheckerTool(),
    PerformanceCheckerTool(),
    ReportGeneratorTool(),
]

__all__ = [
    "GitHubTool",
    "CodeAnalyzerTool",
    "SecurityCheckerTool",
    "PerformanceCheckerTool",
    "ReportGeneratorTool",
    "ALL_TOOLS",
]
```

---

## ✅ FILE 9: `tests/test_tools.py`

**Purpose:** Har tool ka unit test.

```python
import pytest
import asyncio
import os

from tools import (
    GitHubTool,
    CodeAnalyzerTool,
    SecurityCheckerTool,
    PerformanceCheckerTool,
    ReportGeneratorTool,
)

# ── Fixtures ───────────────────────────────────────────────────────────────

SAMPLE_GOOD_CODE = """
def add(a: int, b: int) -> int:
    \"\"\"Two numbers add karo.\"\"\"
    return a + b

def multiply(a: int, b: int) -> int:
    \"\"\"Multiply karo.\"\"\"
    return a * b
"""

SAMPLE_BAD_CODE = """
import os
password = "admin123"

def run_cmd(user_input):
    os.system(user_input)
    eval(user_input)
    result = []
    for i in range(100):
        for j in range(100):
            result.append(i * j)
"""

@pytest.fixture
def good_file(tmp_path):
    f = tmp_path / "good_code.py"
    f.write_text(SAMPLE_GOOD_CODE)
    return str(f)

@pytest.fixture
def bad_file(tmp_path):
    f = tmp_path / "bad_code.py"
    f.write_text(SAMPLE_BAD_CODE)
    return str(f)

# ── Tests ──────────────────────────────────────────────────────────────────

def test_base_tool_schema():
    tool = CodeAnalyzerTool()
    schema = tool.to_schema()
    assert "name" in schema
    assert "description" in schema

@pytest.mark.asyncio
async def test_code_analyzer_good(good_file):
    tool = CodeAnalyzerTool()
    result = await tool.execute(code_path=good_file)
    assert result["status"] == "success"
    assert len(result["data"]["functions"]) == 2
    assert result["data"]["lines_of_code"] > 0

@pytest.mark.asyncio
async def test_security_checker_bad(bad_file):
    tool = SecurityCheckerTool()
    result = await tool.execute(code_path=bad_file)
    assert result["status"] == "success"
    assert result["total_issues"] > 0
    assert result["risk_level"] in ["HIGH", "CRITICAL"]

@pytest.mark.asyncio
async def test_performance_checker_bad(bad_file):
    tool = PerformanceCheckerTool()
    result = await tool.execute(code_path=bad_file)
    assert result["status"] == "success"
    assert result["total_issues"] > 0

@pytest.mark.asyncio
async def test_security_checker_good(good_file):
    tool = SecurityCheckerTool()
    result = await tool.execute(code_path=good_file)
    assert result["status"] == "success"
    assert result["risk_level"] == "SAFE"

@pytest.mark.asyncio
async def test_report_generator():
    tool = ReportGeneratorTool()
    mock_data = {
        "github": {"file_count": 5, "python_file_count": 3, "languages": {".py": 3}},
        "code": {"data": {"functions": [{"name": "f"}], "classes": [],
                          "lines_of_code": 50, "complexity": 3, "has_docstrings": True}},
        "security": {"total_issues": 0, "risk_level": "SAFE", "vulnerabilities": []},
        "performance": {"total_issues": 0, "performance_score": 100, "issues": []}
    }
    result = await tool.execute(analysis_data=mock_data)
    assert result["status"] == "success"
    assert result["report"]["scores"]["overall"] >= 80

@pytest.mark.asyncio
async def test_github_tool_invalid_url():
    tool = GitHubTool()
    result = await tool.execute(github_url="https://github.com/fake/nonexistent-repo-xyz")
    assert result["status"] == "error"
```

**Run tests:**
```bash
pip install pytest pytest-asyncio
pytest tests/test_tools.py -v
```

---

## 🔗 Integration Contract (Person 1 ke saath)

Person 1 (Agent Architect) tumhare tools ko is tarah call karega:

```python
# Agent ka expected usage — DO NOT CHANGE function signatures
from tools import ALL_TOOLS

# Agent tools ko naam se dhundega
tool_map = {t.name: t for t in ALL_TOOLS}

# Tool call pattern
result = await tool_map["fetch_repository"].execute(
    github_url="https://github.com/user/repo"
)

result = await tool_map["analyze_code_structure"].execute(
    code_path="./temp_repo/main.py"
)

result = await tool_map["check_security"].execute(
    code_path="./temp_repo/main.py"
)

result = await tool_map["check_performance"].execute(
    code_path="./temp_repo/main.py"
)

result = await tool_map["generate_report"].execute(
    analysis_data={
        "github": ...,
        "code": ...,
        "security": ...,
        "performance": ...
    }
)
```

**⚠️ Critical Rules:**
- Tool `name` values KABHI mat badlo — Agent in names se tools dhundta hai
- Har tool ka return dict mein `"status"` key HAMESHA hona chahiye
- Koi bhi tool crash nahi hona chahiye — har exception catch karo aur `"status": "error"` return karo
- Sab methods `async` honi chahiyen

---

## 📋 Deliverables Checklist

| File | Status |
|------|--------|
| `tools/__init__.py` | Build karo |
| `tools/base_tool.py` | Build karo |
| `tools/github_tool.py` | Build karo |
| `tools/code_analyzer.py` | Build karo |
| `tools/security_checker.py` | Build karo |
| `tools/performance_checker.py` | Build karo |
| `tools/report_generator.py` | Build karo |
| `tools/utils.py` | Build karo |
| `tests/test_tools.py` | Build karo |

---

## ⚡ Quick Start for opencode

```bash
# 1. Install dependencies
pip install gitpython bandit pylint radon aiofiles pytest pytest-asyncio

# 2. Build all files in tools/ folder as per spec above

# 3. Test individual tool
python -c "
import asyncio
from tools import CodeAnalyzerTool
tool = CodeAnalyzerTool()
result = asyncio.run(tool.execute(code_path='tools/base_tool.py'))
print(result)
"

# 4. Run all tests
pytest tests/test_tools.py -v
```

---

*Spec Kit Version: 1.0 | Role: Tool Engineer (Person 2) | Project: Code Review Agent*
