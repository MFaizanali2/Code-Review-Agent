import ast
from .base_tool import BaseTool

class PerformanceCheckerTool(BaseTool):
    def __init__(self):
        super().__init__(
            name="check_performance",
            description="Python code mein performance issues detect karo"
        )

    async def execute(self, code_path: str) -> dict:
        issues = []

        try:
            with open(code_path, 'r', encoding='utf-8', errors='ignore') as f:
                code = f.read()

            tree = ast.parse(code)

            self._check_nested_loops(tree, issues)
            self._check_loop_appends(tree, issues)
            self._check_global_in_loop(tree, issues)
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
                        break

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
