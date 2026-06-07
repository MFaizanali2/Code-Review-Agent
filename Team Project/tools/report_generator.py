from datetime import datetime
from .base_tool import BaseTool

class ReportGeneratorTool(BaseTool):
    def __init__(self):
        super().__init__(
            name="generate_report",
            description="Sab analysis results ko combine karke final review report banao"
        )

    async def execute(self, analysis_data: dict) -> dict:
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
