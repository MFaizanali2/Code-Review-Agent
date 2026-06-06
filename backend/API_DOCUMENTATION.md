# Code Review Agent API Documentation

Base URL: `http://localhost:8000`

## Endpoints

### Health & Info

| Method | Path | Description |
|--------|------|-------------|
| GET | `/` | Service info (name, version, docs link) |
| GET | `/health` | Health check |

### Reviews

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/review` | Submit code for review (synchronous) |
| POST | `/api/review/async` | Submit code for background review |
| GET | `/api/review/{review_id}` | Get review results by ID |
| GET | `/api/reviews/history` | Get last 20 reviews |

---

## POST `/api/review`

Submit code for synchronous review.

**Request Body:**
```json
{
  "github_url": "https://github.com/user/repo",
  "code_content": "def foo(): pass",
  "analysis_type": "full"
}
```

- `github_url` (optional): GitHub repository URL
- `code_content` (optional): Direct code to review
- `analysis_type`: `full`, `security`, or `performance` (default: `full`)
- At least one of `github_url` or `code_content` is required

**Response (200):**
```json
{
  "status": "success",
  "review_id": "uuid-string",
  "quality_score": 8.5,
  "total_issues": 3,
  "critical_issues": 1,
  "security_issues": 1,
  "performance_issues": 0,
  "issues": [
    {
      "type": "Security",
      "severity": "CRITICAL",
      "message": "SQL injection risk",
      "suggestion": "Use parameterized queries",
      "line_number": 10
    }
  ],
  "report": "Full analysis report text...",
  "timestamp": "2026-01-01T00:00:00"
}
```

**Error (400):** Missing `github_url` and `code_content`
```json
{ "detail": "Either github_url or code_content is required" }
```

---

## POST `/api/review/async`

Submit code for background processing. Returns immediately with a `review_id`.

**Request Body:** Same as `/api/review`

**Response (200):**
```json
{
  "status": "processing",
  "review_id": "uuid-string",
  "message": "Review is being processed in the background"
}
```

---

## GET `/api/review/{review_id}`

Retrieve a completed review.

**Response (200):**
```json
{
  "review_id": "uuid-string",
  "quality_score": 8.5,
  "total_issues": 3,
  "report": "...",
  "timestamp": "2026-01-01T00:00:00"
}
```

**Error (404):**
```json
{ "detail": "Review not found" }
```

---

## GET `/api/reviews/history`

Get the 20 most recent reviews.

**Response (200):**
```json
[
  {
    "review_id": "uuid-string",
    "code_source": "direct",
    "quality_score": 8.5,
    "total_issues": 3,
    "timestamp": "2026-01-01T00:00:00"
  }
]
```

---

## Running the Server

```bash
# From project root
python -m backend.main

# Or
cd backend && python main.py
```

Open `http://localhost:8000/docs` for interactive Swagger UI.

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `LLM_PROVIDER` | `mock` | `mock`, `gemini`, or `openai` |
| `GEMINI_API_KEY` | - | Required when using Gemini |
| `OPENAI_API_KEY` | - | Required when using OpenAI |
| `DATABASE_URL` | `sqlite:///./reviews.db` | SQLite database path |
| `API_HOST` | `0.0.0.0` | Server bind address |
| `API_PORT` | `8000` | Server port |
| `API_DEBUG` | `false` | Enable debug mode |
