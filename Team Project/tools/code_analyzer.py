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

            if (tree.body and isinstance(tree.body[0], ast.Expr)
                    and isinstance(tree.body[0].value, ast.Constant)):
                analysis["has_docstrings"] = True

            return {"status": "success", "data": analysis}

        except SyntaxError as e:
            return {"status": "error", "message": f"Syntax error in file: {str(e)}"}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def _calculate_complexity(self, tree: ast.AST) -> int:
        complexity = 1
        for node in ast.walk(tree):
            if isinstance(node, (
                ast.If, ast.While, ast.For,
                ast.ExceptHandler, ast.With,
                ast.Assert, ast.comprehension
            )):
                complexity += 1
        return complexity
