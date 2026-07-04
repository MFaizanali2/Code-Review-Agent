import ast
import os
from agent.tools.base import BaseTool, ToolResult, ToolSchema


class CodeAnalyzerTool(BaseTool):
    @property
    def name(self) -> str:
        return "analyze_code_structure"

    @property
    def description(self) -> str:
        return "Analyze a Python file's structure: functions, classes, imports, complexity"

    async def run(self, tool_input: dict) -> ToolResult:
        code_path = tool_input.get("code_path", "")
        if not code_path:
            return ToolResult(success=False, data={}, error="code_path is required")
        if not os.path.isfile(code_path):
            return ToolResult(success=False, data={}, error=f"File not found: {code_path}")

        try:
            with open(code_path, "r", encoding="utf-8", errors="ignore") as f:
                code = f.read()

            tree = ast.parse(code)

            analysis = {
                "file": code_path,
                "functions": [],
                "classes": [],
                "imports": [],
                "lines_of_code": len(code.splitlines()),
                "complexity": self._calculate_complexity(tree),
                "has_docstrings": False,
            }

            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    has_doc = (
                        isinstance(node.body[0], ast.Expr)
                        and isinstance(node.body[0].value, ast.Constant)
                        if node.body
                        else False
                    )
                    analysis["functions"].append({
                        "name": node.name,
                        "line": node.lineno,
                        "args_count": len(node.args.args),
                        "has_docstring": has_doc,
                    })

                elif isinstance(node, ast.ClassDef):
                    analysis["classes"].append({
                        "name": node.name,
                        "line": node.lineno,
                        "method_count": len([
                            n for n in node.body if isinstance(n, ast.FunctionDef)
                        ]),
                    })

                elif isinstance(node, (ast.Import, ast.ImportFrom)):
                    analysis["imports"].append(ast.unparse(node))

            if (
                tree.body
                and isinstance(tree.body[0], ast.Expr)
                and isinstance(tree.body[0].value, ast.Constant)
            ):
                analysis["has_docstrings"] = True

            return ToolResult(success=True, data={"status": "success", "data": analysis})

        except SyntaxError as e:
            return ToolResult(success=False, data={}, error=f"Syntax error in file: {str(e)}")
        except Exception as e:
            return ToolResult(success=False, data={}, error=str(e))

    def _calculate_complexity(self, tree: ast.AST) -> int:
        complexity = 1
        for node in ast.walk(tree):
            if isinstance(node, (
                ast.If,
                ast.While,
                ast.For,
                ast.ExceptHandler,
                ast.With,
                ast.Assert,
                ast.comprehension,
            )):
                complexity += 1
        return complexity

    def schema(self) -> ToolSchema:
        return ToolSchema(
            name=self.name,
            description=self.description,
            parameters={
                "code_path": {
                    "type": "string",
                    "description": "Path to the Python file to analyze",
                },
            },
            required=["code_path"],
        )
