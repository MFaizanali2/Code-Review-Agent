import json
import re
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class ParsedReview:
    def __init__(self):
        self.quality_score: int = 0
        self.critical_issues: list[dict] = []
        self.major_issues: list[dict] = []
        self.minor_issues: list[dict] = []
        self.recommendations: list[str] = []
        self.summary: str = ""
        self.raw_text: str = ""
        self.parsing_method: str = "markdown"

    def to_dict(self) -> dict:
        return {
            "quality_score": self.quality_score,
            "critical_issues": self.critical_issues,
            "major_issues": self.major_issues,
            "minor_issues": self.minor_issues,
            "recommendations": self.recommendations,
            "summary": self.summary,
            "total_issues": len(self.critical_issues) + len(self.major_issues) + len(self.minor_issues),
        }

    @property
    def all_issues(self) -> list[dict]:
        return self.critical_issues + self.major_issues + self.minor_issues


def parse_llm_response(response_text: str) -> ParsedReview:
    result = ParsedReview()
    result.raw_text = response_text

    if not response_text or not response_text.strip():
        logger.warning("Empty response received")
        result.summary = "No response received from LLM."
        return result

    if response_text.strip().startswith("{"):
        try:
            _parse_json_format(response_text, result)
            result.parsing_method = "json"
            if _validate_result(result):
                return result
        except json.JSONDecodeError:
            logger.debug("JSON parsing failed, trying markdown")

    _parse_markdown_format(response_text, result)
    result.parsing_method = "markdown"

    if result.quality_score == 0 and not result.all_issues:
        logger.debug("Markdown parsing incomplete, using fallback")
        _parse_fallback(response_text, result)
        result.parsing_method = "fallback"

    _validate_and_fix(result)
    return result


def _parse_json_format(text: str, result: ParsedReview):
    data = json.loads(text)
    if "quality_score" in data:
        result.quality_score = int(data["quality_score"])
    for severity_key, target_list in [("critical_issues", result.critical_issues), ("major_issues", result.major_issues), ("minor_issues", result.minor_issues), ("issues", None)]:
        issues = data.get(severity_key, [])
        if issues and target_list is not None:
            for issue in issues:
                if isinstance(issue, str):
                    target_list.append({"message": issue, "severity": severity_key.replace("_", " ").title()})
                elif isinstance(issue, dict):
                    target_list.append(issue)
    if "issues" in data and not result.critical_issues:
        for issue in data["issues"]:
            severity = issue.get("severity", "LOW").upper()
            entry = {"message": issue.get("message", ""), "severity": severity, "type": issue.get("type", "General"), "line_number": issue.get("line_number"), "suggestion": issue.get("suggestion", issue.get("fix", ""))}
            if severity == "CRITICAL":
                result.critical_issues.append(entry)
            elif severity in ("HIGH", "MAJOR"):
                result.major_issues.append(entry)
            else:
                result.minor_issues.append(entry)
    result.recommendations = data.get("recommendations", data.get("suggestions", []))
    result.summary = data.get("summary", data.get("description", ""))


def _parse_markdown_format(text: str, result: ParsedReview):
    score_patterns = [
        r"(?:quality\s+)?score\s*[:：]\s*(\d+)\s*/?\s*100",
        r"(\d+)\s*/?\s*100",
        r"score[:\s]*(\d+)",
        r"(\d+)\s*points?",
    ]
    for pattern in score_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            score = int(match.group(1))
            if 0 <= score <= 100:
                result.quality_score = score
                break

    sections = {"critical": result.critical_issues, "major": result.major_issues, "minor": result.minor_issues}
    section_pattern = re.compile(r"(?:^|\n)#{1,4}\s*(.*?)\n(.*?)(?=\n#{1,4}\s|\Z)", re.DOTALL | re.IGNORECASE)
    for match in section_pattern.finditer(text):
        header = match.group(1).strip().lower()
        content = match.group(2).strip()
        for section_name, target_list in sections.items():
            if section_name in header:
                items = _extract_issues_from_section(content)
                target_list.extend(items)

    rec_patterns = [r"(?:recommendation|suggestion|quick[\s-]?wins)[\s\S]*?(?=\n#{1,4}\s|\Z)"]
    for pattern in rec_patterns:
        match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
        if match:
            result.recommendations = _extract_recommendations(match.group(0))

    summary_match = re.search(r"(?:summary|overview)[:\s]*\n*(.*?)(?=\n#{1,4}\s|\Z)", text, re.DOTALL | re.IGNORECASE)
    if summary_match:
        result.summary = summary_match.group(1).strip()[:500]


def _extract_issues_from_section(section_text: str) -> list[dict]:
    issues = []
    lines = section_text.split("\n")
    current_issue = None
    for line in lines:
        line = line.strip()
        if not line:
            continue
        issue_match = re.match(r"^[\s]*[-•*]\s*(.*?)(?:\s*[-–—]\s*|\s*:?\s*Line\s*(\d+))?", line, re.IGNORECASE)
        numbered_match = re.match(r"^\s*\d+[.)]\s*(.*)", line)
        if issue_match or numbered_match:
            if current_issue:
                issues.append(_finalize_issue(current_issue))
            text = (issue_match or numbered_match).group(1)
            line_num = None
            line_num_match = re.search(r"line\s*:?\s*(\d+)", text, re.IGNORECASE)
            if line_num_match:
                line_num = int(line_num_match.group(1))
                text = text[: line_num_match.start()].strip()
            severity = "MAJOR"
            severity_match = re.search(r"\b(CRITICAL|HIGH|MEDIUM|LOW)\b", text, re.IGNORECASE)
            if severity_match:
                severity = severity_match.group(1).upper()
                text = text.replace(severity_match.group(0), "").strip()
                text = re.sub(r"^[-–—:\s]+", "", text)
            current_issue = {"message": text, "severity": severity, "line_number": line_num}
        elif current_issue:
            current_issue["message"] += " " + line.strip()
    if current_issue:
        issues.append(_finalize_issue(current_issue))
    return issues


def _finalize_issue(issue: dict) -> dict:
    issue["message"] = issue["message"].strip().rstrip(".,;:")
    issue["message"] = issue["message"][:200]
    suggestion_match = re.search(r"(?:fix|suggestion|use|try)[:\s]+(.*)", issue["message"], re.IGNORECASE)
    if suggestion_match:
        issue["suggestion"] = suggestion_match.group(1).strip()
        issue["message"] = issue["message"][: suggestion_match.start()].strip()
    issue.setdefault("severity", "MAJOR")
    issue.setdefault("type", "General")
    return issue


def _extract_recommendations(text: str) -> list[str]:
    recs = []
    lines = text.split("\n")
    for line in lines:
        line = line.strip()
        if not line:
            continue
        match = re.match(r"^[\s]*[-•*\d+.)\s]+(.*)", line)
        if match:
            rec = match.group(1).strip()
            if len(rec) > 10:
                recs.append(rec)
    return recs[:10]


def _parse_fallback(text: str, result: ParsedReview):
    lines = text.split("\n")
    for line in lines:
        score_match = re.search(r"(\d{1,3})\s*(?:/100|points|score)", line, re.IGNORECASE)
        if score_match:
            score = int(score_match.group(1))
            if 0 <= score <= 100:
                result.quality_score = score
                break
    for line in lines:
        line = line.strip()
        if len(line) > 30 and not line.startswith("#") and not line.startswith("```"):
            severity = "MAJOR"
            if any(word in line.lower() for word in ["critical", "danger", "vulnerability"]):
                severity = "CRITICAL"
            elif any(word in line.lower() for word in ["minor", "style", "nit"]):
                severity = "MINOR"
            result.minor_issues.append({"message": line[:200], "severity": severity})
    if lines:
        result.summary = lines[0].strip()[:300]


def _validate_result(result: ParsedReview) -> bool:
    has_score = 0 <= result.quality_score <= 100
    has_issues = bool(result.critical_issues or result.major_issues or result.minor_issues)
    has_recs = bool(result.recommendations)
    return has_score or has_issues


def _validate_and_fix(result: ParsedReview):
    if not (0 <= result.quality_score <= 100):
        result.quality_score = 50
    result.critical_issues.sort(key=lambda x: x.get("line_number", 9999) or 9999)
    result.major_issues.sort(key=lambda x: x.get("line_number", 9999) or 9999)
    result.minor_issues.sort(key=lambda x: x.get("line_number", 9999) or 9999)
    result.critical_issues = result.critical_issues[:20]
    result.major_issues = result.major_issues[:30]
    result.minor_issues = result.minor_issues[:30]
    if not result.summary:
        result.summary = f"Review complete. Score: {result.quality_score}/100. Found {len(result.all_issues)} issues."
