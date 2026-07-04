def get_tool_schemas() -> list[dict]:
    return [
        _github_tool_schema(),
        _code_analyzer_schema(),
        _security_checker_schema(),
        _performance_checker_schema(),
        _report_generator_schema(),
        _file_reader_schema(),
    ]


def _github_tool_schema() -> dict:
    return {
        "name": "fetch_repository",
        "description": (
            "GitHub se repository clone karta hai aur file list return karta hai. "
            "Sirf PUBLIC repositories support hain. "
            "Repository URL full hona chahiye (https://github.com/username/repo)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "github_url": {
                    "type": "string",
                    "description": "Full GitHub repository URL. Example: 'https://github.com/psf/black'",
                    "pattern": r"^https://github\.com/[\w.-]+/[\w.-]+/?$",
                },
                "branch": {
                    "type": "string",
                    "description": "Branch ya tag name (default: auto-detect). Example: 'main', 'develop'",
                    "default": "main",
                },
                "depth": {
                    "type": "integer",
                    "description": "Clone depth for faster cloning. 0 = full clone.",
                    "default": 1,
                    "minimum": 0,
                    "maximum": 100,
                },
            },
            "required": ["github_url"],
        },
    }


def _code_analyzer_schema() -> dict:
    return {
        "name": "analyze_code_structure",
        "description": (
            "Kisi bhi Python file ka structure analyze karta hai. "
            "Functions, classes, imports, aur complexity nikalta hai. "
            "Sirf .py files support hain."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Analyze karne ke liye file ka relative path. Example: 'src/main.py'",
                },
                "include_ast": {
                    "type": "boolean",
                    "description": "AST details bhi include karein? (default: false)",
                    "default": False,
                },
            },
            "required": ["file_path"],
        },
    }


def _security_checker_schema() -> dict:
    return {
        "name": "security_audit",
        "description": (
            "Code mein security vulnerabilities detect karta hai. "
            "Checks: SQL injection, hardcoded secrets, eval/exec usage, "
            "command injection, path traversal, unsafe deserialization."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "File ka path jiska security audit karna hai.",
                },
                "severity_threshold": {
                    "type": "string",
                    "description": "Minimum severity to report. Options: 'LOW', 'MEDIUM', 'HIGH', 'CRITICAL'",
                    "enum": ["LOW", "MEDIUM", "HIGH", "CRITICAL"],
                    "default": "LOW",
                },
            },
            "required": ["file_path"],
        },
    }


def _performance_checker_schema() -> dict:
    return {
        "name": "performance_analysis",
        "description": (
            "Performance bottlenecks identify karta hai. "
            "Checks: nested loops, O(n²) complexity, "
            "memory leaks, string concat in loops, large allocations."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "File ka path jiska performance analysis karna hai.",
                },
                "detailed": {
                    "type": "boolean",
                    "description": "Detailed analysis with line numbers? (default: false)",
                    "default": False,
                },
            },
            "required": ["file_path"],
        },
    }


def _report_generator_schema() -> dict:
    return {
        "name": "generate_report",
        "description": (
            "Saare findings ko ek structured report mein convert karta hai. "
            "Report mein score, issues, recommendations, aur code examples hote hain."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "findings": {
                    "type": "array",
                    "description": "All findings from security, performance, and analysis tools.",
                    "items": {"type": "object"},
                },
                "format": {
                    "type": "string",
                    "description": "Report format. Options: 'markdown', 'json'",
                    "enum": ["markdown", "json"],
                    "default": "markdown",
                },
                "include_code_examples": {
                    "type": "boolean",
                    "description": "Fix examples include karein? (default: true)",
                    "default": True,
                },
            },
            "required": ["findings"],
        },
    }


def _file_reader_schema() -> dict:
    return {
        "name": "read_file_content",
        "description": (
            "Kisi bhi file ka content read karta hai. "
            "Binary files skip ho jayenge. Sirf text files support hain."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "File ka path jo read karna hai.",
                },
                "max_lines": {
                    "type": "integer",
                    "description": "Maximum lines to read (0 = all).",
                    "default": 0,
                    "minimum": 0,
                    "maximum": 5000,
                },
            },
            "required": ["file_path"],
        },
    }


TOOL_CATEGORIES = {
    "code_fetching": ["fetch_repository"],
    "code_analysis": ["analyze_code_structure", "read_file_content"],
    "security": ["security_audit"],
    "performance": ["performance_analysis"],
    "reporting": ["generate_report"],
}


def get_simplified_tools() -> list[dict]:
    return [
        {"name": "fetch_repository", "description": "GitHub se code fetch karein", "input_schema": {"type": "object", "properties": {"github_url": {"type": "string"}}, "required": ["github_url"]}},
        {"name": "analyze_code_structure", "description": "Code structure analyze karein", "input_schema": {"type": "object", "properties": {"file_path": {"type": "string"}}, "required": ["file_path"]}},
        {"name": "security_audit", "description": "Security check karein", "input_schema": {"type": "object", "properties": {"file_path": {"type": "string"}}, "required": ["file_path"]}},
        {"name": "performance_analysis", "description": "Performance check karein", "input_schema": {"type": "object", "properties": {"file_path": {"type": "string"}}, "required": ["file_path"]}},
    ]
