"""
Test Suite — CodeSense AI Frontend
Person 5: Frontend + DevOps

Tests cover:
- API Client methods
- Mock data generation
- Health check logic
- Report generation
"""

import pytest
from unittest.mock import patch, MagicMock
import sys
import os
import requests as req

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__))))
from api_client import APIClient


# ─── Fixtures ────────────────────────────────────────────────────────────────
@pytest.fixture
def client() -> APIClient:
    return APIClient("http://localhost:8000")


@pytest.fixture
def mock_review_response() -> dict:
    return {
        "status": "success",
        "overall_score": 78,
        "files_analyzed": 15,
        "lines_of_code": 1200,
        "critical_issues": 2,
        "warnings": 5,
        "security_issues": [],
        "performance_issues": [],
        "quality_metrics": {
            "maintainability": 80,
            "readability": 75,
            "test_coverage": 55,
            "documentation": 60,
            "complexity": 70,
            "modularity": 85
        },
        "suggestions": ["Add type hints", "Increase test coverage"],
        "full_report": "# Test Report"
    }


# ─── Health Check Tests ───────────────────────────────────────────────────────
class TestHealthCheck:
    def test_health_check_success(self, client) -> None:
        with patch("requests.get") as mock_get:
            mock_get.return_value = MagicMock(status_code=200)
            assert client.health_check() is True

    def test_health_check_failure_404(self, client) -> None:
        with patch("requests.get") as mock_get:
            mock_get.return_value = MagicMock(status_code=404)
            assert client.health_check() is False

    def test_health_check_connection_error(self, client) -> None:
        with patch("requests.get", side_effect=Exception("Connection refused")):
            assert client.health_check() is False


# ─── Review Code Tests ────────────────────────────────────────────────────────
class TestReviewCode:
    def test_review_with_github_url(self, client, mock_review_response) -> None:
        with patch("requests.post") as mock_post:
            mock_post.return_value = MagicMock(
                status_code=200,
                json=lambda: mock_review_response
            )
            mock_post.return_value.raise_for_status = lambda: None

            result = client.review_code(github_url="https://github.com/test/repo")
            assert result is not None
            assert result["status"] == "success"
            assert result["overall_score"] == 78

    def test_review_with_code_content(self, client, mock_review_response) -> None:
        with patch("requests.post") as mock_post:
            mock_post.return_value = MagicMock(
                status_code=200,
                json=lambda: mock_review_response
            )
            mock_post.return_value.raise_for_status = lambda: None

            result = client.review_code(code_content="def hello(): pass")
            assert result is not None
            assert result["files_analyzed"] == 15

    def test_review_returns_none_on_connection_error(self, client) -> None:
        with patch("requests.post", side_effect=req.exceptions.ConnectionError()):
            result = client.review_code(github_url="https://github.com/test/repo")
            assert result is None

    def test_review_payload_contains_model(self, client, mock_review_response) -> None:
        with patch("requests.post") as mock_post:
            mock_post.return_value = MagicMock(
                status_code=200,
                json=lambda: mock_review_response
            )
            mock_post.return_value.raise_for_status = lambda: None

            client.review_code(
                github_url="https://github.com/test/repo",
                model="gemini-2.0-flash",
                depth="Deep"
            )
            call_args = mock_post.call_args
            payload = call_args[1]["json"]
            assert payload["model"] == "gemini-2.0-flash"
            assert payload["depth"] == "Deep"


# ─── Mock Data Tests ──────────────────────────────────────────────────────────
class TestMockData:
    def test_mock_result_has_required_keys(self, client) -> None:
        result = client.get_mock_result({"github_url": "https://github.com/test/repo"})
        required_keys = [
            "status", "overall_score", "files_analyzed", "lines_of_code",
            "critical_issues", "warnings", "security_issues",
            "performance_issues", "quality_metrics", "suggestions", "full_report"
        ]
        for key in required_keys:
            assert key in result, f"Missing key: {key}"

    def test_mock_score_in_valid_range(self, client) -> None:
        for _ in range(10):
            result = client.get_mock_result({})
            score = result["overall_score"]
            assert 55 <= score <= 92, f"Score {score} out of range"

    def test_mock_security_issues_have_severity(self, client) -> None:
        result = client.get_mock_result({})
        for issue in result["security_issues"]:
            assert "severity" in issue
            assert issue["severity"] in ["critical", "warning", "good", "info"]

    def test_mock_quality_metrics_all_present(self, client) -> None:
        result = client.get_mock_result({})
        metrics = result["quality_metrics"]
        expected = ["maintainability", "readability", "test_coverage",
                    "documentation", "complexity", "modularity"]
        for m in expected:
            assert m in metrics

    def test_full_report_contains_score(self, client) -> None:
        result = client.get_mock_result({"github_url": "https://github.com/test/repo"})
        report = result["full_report"]
        assert str(result["overall_score"]) in report

    def test_demo_mode_flag_is_true(self, client) -> None:
        result = client.get_mock_result({})
        assert result.get("demo_mode") is True


# ─── History Tests ────────────────────────────────────────────────────────────
class TestHistory:
    def test_get_history_returns_list(self, client) -> None:
        with patch("requests.get") as mock_get:
            mock_get.return_value = MagicMock(
                status_code=200,
                json=lambda: [{"id": 1}, {"id": 2}]
            )
            mock_get.return_value.raise_for_status = lambda: None

            history = client.get_history()
            assert isinstance(history, list)
            assert len(history) == 2

    def test_get_history_returns_empty_on_error(self, client) -> None:
        with patch("requests.get", side_effect=Exception("Error")):
            history = client.get_history()
            assert history == []


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])