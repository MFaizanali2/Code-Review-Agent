"""Comprehensive integration tests for the FastAPI backend (50 tests)."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from backend.database import Base, engine
from backend.main import app


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def _setup_db():
    """Fresh database tables for each test."""
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client():
    """FastAPI TestClient instance."""
    with TestClient(app) as c:
        yield c


# ── 1. Health & Root Endpoints (5 tests) ─────────────────────────────────────


class TestRootAndHealth:
    """GET / and GET /health"""

    def test_01_root_returns_service_info(self, client):
        resp = client.get("/")
        assert resp.status_code == 200
        body = resp.json()
        assert body["name"] == "Code Review Agent API"
        assert body["version"] == "1.0.0"
        assert body["docs"] == "/docs"

    def test_02_root_has_correct_structure(self, client):
        resp = client.get("/")
        assert set(resp.json().keys()) == {"name", "version", "docs"}

    def test_03_health_returns_ok(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

    def test_04_health_has_message(self, client):
        resp = client.get("/health")
        body = resp.json()
        assert "message" in body
        assert isinstance(body["message"], str)

    def test_05_health_structure(self, client):
        resp = client.get("/health")
        assert set(resp.json().keys()) == {"status", "message"}


# ── 2. Review Input Validation (10 tests) ────────────────────────────────────


class TestReviewValidation:
    """POST /api/review — input validation"""

    def test_06_missing_both_inputs_returns_400(self, client):
        resp = client.post("/api/review", json={"analysis_type": "full"})
        assert resp.status_code == 400
        assert "required" in resp.json()["detail"]

    def test_07_empty_github_url_returns_400(self, client):
        resp = client.post("/api/review", json={"github_url": "", "analysis_type": "full"})
        assert resp.status_code == 400

    def test_08_empty_code_content_returns_400(self, client):
        resp = client.post("/api/review", json={"code_content": "", "analysis_type": "full"})
        assert resp.status_code == 400

    def test_09_whitespace_only_code_allowed(self, client):
        resp = client.post("/api/review", json={"code_content": "   ", "analysis_type": "full"})
        assert resp.status_code == 200

    def test_10_null_github_url_returns_400(self, client):
        resp = client.post("/api/review", json={"github_url": None, "analysis_type": "full"})
        assert resp.status_code == 400

    def test_11_null_code_content_returns_400(self, client):
        resp = client.post("/api/review", json={"code_content": None, "analysis_type": "full"})
        assert resp.status_code == 400

    def test_12_empty_body_returns_400(self, client):
        resp = client.post("/api/review", json={})
        assert resp.status_code == 400

    def test_13_invalid_json_returns_422(self, client):
        resp = client.post("/api/review", data="not-json", headers={"Content-Type": "application/json"})
        assert resp.status_code == 422

    def test_14_extra_fields_ignored(self, client):
        resp = client.post("/api/review", json={
            "code_content": "x = 1",
            "extra_field": "should_be_ignored",
        })
        assert resp.status_code == 200

    def test_15_wrong_type_for_analysis_type_rejected(self, client):
        resp = client.post("/api/review", json={
            "code_content": "x = 1",
            "analysis_type": 123,
        })
        assert resp.status_code == 422


# ── 3. Review Creation – Code Content (8 tests) ──────────────────────────────


class TestReviewWithCode:
    """POST /api/review with code_content"""

    def test_16_simple_code_review_succeeds(self, client):
        resp = client.post("/api/review", json={"code_content": "def add(a, b): return a + b"})
        assert resp.status_code == 200
        assert resp.json()["status"] == "success"

    def test_17_review_returns_review_id(self, client):
        resp = client.post("/api/review", json={"code_content": "x = 1"})
        body = resp.json()
        assert "review_id" in body
        assert len(body["review_id"]) > 10

    def test_18_review_returns_quality_score(self, client):
        resp = client.post("/api/review", json={"code_content": "x = 1"})
        body = resp.json()
        assert "quality_score" in body
        assert 0.0 <= body["quality_score"] <= 10.0

    def test_19_review_returns_issues_list(self, client):
        resp = client.post("/api/review", json={"code_content": "x = 1"})
        assert "issues" in resp.json()

    def test_20_review_returns_report(self, client):
        resp = client.post("/api/review", json={"code_content": "x = 1"})
        assert isinstance(resp.json()["report"], str)

    def test_21_review_returns_timestamp(self, client):
        resp = client.post("/api/review", json={"code_content": "x = 1"})
        assert "timestamp" in resp.json()

    def test_22_review_with_security_analysis_type(self, client):
        resp = client.post("/api/review", json={
            "code_content": "exec(input())",
            "analysis_type": "security",
        })
        assert resp.status_code == 200

    def test_23_review_with_performance_analysis_type(self, client):
        resp = client.post("/api/review", json={
            "code_content": "for i in range(1000): print(i)",
            "analysis_type": "performance",
        })
        assert resp.status_code == 200


# ── 4. Review Creation – GitHub URL (5 tests) ────────────────────────────────


class TestReviewWithGithub:
    """POST /api/review with github_url"""

    def test_24_github_url_review_succeeds(self, client):
        resp = client.post("/api/review", json={
            "github_url": "https://github.com/user/repo",
        })
        assert resp.status_code == 200

    def test_25_github_url_returns_review_id(self, client):
        resp = client.post("/api/review", json={"github_url": "https://github.com/user/repo"})
        assert len(resp.json()["review_id"]) > 10

    def test_26_github_url_with_security_analysis(self, client):
        resp = client.post("/api/review", json={
            "github_url": "https://github.com/user/repo",
            "analysis_type": "security",
        })
        assert resp.status_code == 200

    def test_27_github_url_with_performance_analysis(self, client):
        resp = client.post("/api/review", json={
            "github_url": "https://github.com/user/repo",
            "analysis_type": "performance",
        })
        assert resp.status_code == 200

    def test_28_complex_github_url_works(self, client):
        resp = client.post("/api/review", json={
            "github_url": "https://github.com/org/repo-name/subdir/blob/main/file.py",
        })
        assert resp.status_code == 200


# ── 5. Review Retrieval (8 tests) ────────────────────────────────────────────


class TestReviewRetrieval:
    """GET /api/review/{review_id}"""

    def test_29_get_nonexistent_review_returns_404(self, client):
        resp = client.get("/api/review/nonexistent-id-12345")
        assert resp.status_code == 404
        assert resp.json()["detail"] == "Review not found"

    def test_30_get_nonexistent_with_uuid_format(self, client):
        resp = client.get("/api/review/aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee")
        assert resp.status_code == 404

    def test_31_get_empty_review_id_returns_405(self, client):
        resp = client.get("/api/review/")
        assert resp.status_code == 405

    def test_32_get_review_after_creation_returns_data(self, client):
        create = client.post("/api/review", json={"code_content": "x = 1"})
        rid = create.json()["review_id"]
        resp = client.get(f"/api/review/{rid}")
        assert resp.status_code == 200

    def test_33_get_review_matches_creation(self, client):
        create = client.post("/api/review", json={"code_content": "x = 1"})
        cbody = create.json()
        rid = cbody["review_id"]

        resp = client.get(f"/api/review/{rid}")
        gbody = resp.json()
        assert gbody["review_id"] == rid
        assert gbody["quality_score"] == cbody["quality_score"]

    def test_34_get_review_has_all_fields(self, client):
        create = client.post("/api/review", json={"code_content": "x = 1"})
        rid = create.json()["review_id"]
        resp = client.get(f"/api/review/{rid}")
        keys = set(resp.json().keys())
        assert keys == {"review_id", "quality_score", "total_issues", "report", "timestamp"}

    def test_35_get_review_timestamp_is_iso_format(self, client):
        create = client.post("/api/review", json={"code_content": "x = 1"})
        rid = create.json()["review_id"]
        resp = client.get(f"/api/review/{rid}")
        ts = resp.json()["timestamp"]
        datetime.fromisoformat(ts.replace("Z", "+00:00"))

    def test_36_get_review_quality_score_is_float(self, client):
        create = client.post("/api/review", json={"code_content": "x = 1"})
        rid = create.json()["review_id"]
        resp = client.get(f"/api/review/{rid}")
        assert isinstance(resp.json()["quality_score"], (int, float))


# ── 6. Review History (7 tests) ──────────────────────────────────────────────


class TestReviewHistory:
    """GET /api/reviews/history"""

    def test_37_empty_history_returns_empty_list(self, client):
        resp = client.get("/api/reviews/history")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_38_history_returns_list(self, client):
        resp = client.get("/api/reviews/history")
        assert isinstance(resp.json(), list)

    def test_39_history_after_one_review(self, client):
        client.post("/api/review", json={"code_content": "a = 1"})
        resp = client.get("/api/reviews/history")
        assert len(resp.json()) == 1

    def test_40_history_after_multiple_reviews(self, client):
        for i in range(5):
            client.post("/api/review", json={"code_content": f"x = {i}"})
        resp = client.get("/api/reviews/history")
        assert len(resp.json()) == 5

    def test_41_history_max_limit_20(self, client):
        for i in range(30):
            client.post("/api/review", json={"code_content": f"x = {i}"})
        resp = client.get("/api/reviews/history")
        assert len(resp.json()) <= 20

    def test_42_history_items_have_required_fields(self, client):
        client.post("/api/review", json={"code_content": "x = 1"})
        item = client.get("/api/reviews/history").json()[0]
        assert set(item.keys()) == {"review_id", "code_source", "quality_score", "total_issues", "timestamp"}

    def test_43_history_items_ordered_by_timestamp_desc(self, client):
        for i in range(3):
            client.post("/api/review", json={"code_content": f"x = {i}"})
        items = client.get("/api/reviews/history").json()
        timestamps = [datetime.fromisoformat(i["timestamp"].replace("Z", "+00:00")) for i in items]
        assert timestamps == sorted(timestamps, reverse=True)


# ── 7. Async Review (6 tests) ────────────────────────────────────────────────


class TestAsyncReview:
    """POST /api/review/async"""

    def test_44_async_review_returns_processing(self, client):
        resp = client.post("/api/review/async", json={"code_content": "x = 1"})
        assert resp.status_code == 200
        assert resp.json()["status"] == "processing"

    def test_45_async_review_returns_review_id(self, client):
        resp = client.post("/api/review/async", json={"code_content": "x = 1"})
        assert len(resp.json()["review_id"]) > 10

    def test_46_async_review_has_message(self, client):
        resp = client.post("/api/review/async", json={"code_content": "x = 1"})
        assert "message" in resp.json()

    def test_47_async_review_missing_input_returns_400(self, client):
        resp = client.post("/api/review/async", json={"analysis_type": "full"})
        assert resp.status_code == 400

    def test_48_async_review_with_github_url(self, client):
        resp = client.post("/api/review/async", json={
            "github_url": "https://github.com/user/repo",
        })
        assert resp.status_code == 200
        assert resp.json()["status"] == "processing"

    def test_49_async_review_returns_uuid_format(self, client):
        import uuid
        resp = client.post("/api/review/async", json={"code_content": "x = 1"})
        rid = resp.json()["review_id"]
        uuid.UUID(rid)


# ── 8. CORS & Edge Cases (1 test) ────────────────────────────────────────────


class TestCorsAndEdgeCases:
    """CORS headers and miscellaneous edge cases"""

    def test_50_cors_headers_present(self, client):
        resp = client.options("/api/review", headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "POST",
        })
        assert resp.status_code == 200
        assert resp.headers.get("access-control-allow-origin") == "http://localhost:3000"
        assert "POST" in resp.headers.get("access-control-allow-methods", "")
        assert resp.headers.get("access-control-allow-credentials") == "true"
