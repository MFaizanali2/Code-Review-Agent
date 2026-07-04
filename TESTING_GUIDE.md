# Code Review Agent - Testing Guide

## Part 1: Backend Startup

Open **Terminal 1** (PowerShell) and run:

```powershell
cd G:\Code-Review-Agent\project-github

# Create + activate virtual environment (first time only)
python -m venv venv
.\venv\Scripts\Activate

# Install dependencies (first time only)
pip install -r requirements.txt

# Copy environment config (first time only)
copy .env.example .env

# Start the backend server
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
```

**Expected output:**
```
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8000
```

The server is ready when you see "Application startup complete". Keep this terminal running.

---

## Part 2: Frontend Startup

Open **Terminal 2** (separate PowerShell window) and run:

```powershell
cd G:\Code-Review-Agent\project-github
.\venv\Scripts\Activate
streamlit run frontend/streamlit_app.py
```

**Expected output:**
```
Local URL: http://localhost:8501
Network URL: http://192.168.x.x:8501
```

Streamlit opens automatically at `http://localhost:8501`. Keep this terminal running.

---

## Part 3: Browser Testing Steps

### Test 1: API Health Check

| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Go to `http://localhost:8000/health` | `{"status":"ok","message":"Server is running"}` |
| 2 | Go to `http://localhost:8000/` | JSON with service name and version |
| 3 | **Result** | API is live |

### Test 2: API Documentation

| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Go to `http://localhost:8000/docs` | Swagger UI loads with all endpoints listed |
| 2 | Expand **POST /api/review** | See request schema with `github_url` and `code_content` fields |
| 3 | Click "Try it out", enter `{"github_url": "https://github.com/torvalds/linux"}`, click Execute | Review runs and returns results |
| 4 | **Result** | API docs + endpoint working |

### Test 3: Frontend Loads

| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Go to `http://localhost:8501` | "CodeSense AI" hero title with gradient text |
| 2 | Check UI elements | Two input tabs: "GitHub Repository" and "Paste Code" |
| 3 | Check sidebar | API endpoint field, model selector, review depth slider |
| 4 | **Result** | Frontend UI loaded |

### Test 4: GitHub URL Review

| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | In "GitHub Repository" tab, enter `https://github.com/torvalds/linux` | Repository detected card appears |
| 2 | Click **Analyze** button | "AGENT ANALYZING CODE..." progress animation |
| 3 | After ~5-10 seconds | Results section appears with score cards |
| 4 | Observe score | Overall Score, Files Analyzed, Lines of Code, Critical Issues counters |
| 5 | Scroll through tabs | Security, Performance, Code Quality, Full Report tabs populated |
| 6 | **Result** | Full review flow works |

### Test 5: Direct Code Input

| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Switch to **Paste Code** tab | Text area appears |
| 2 | Paste this vulnerable Python code: |

```python
def process(data):
    for i in range(len(data)):
        for j in range(len(data)):
            print(data[i], data[j])

API_KEY = "sk-1234567890abcdef"

import subprocess
user_input = request.GET.get("cmd")
subprocess.call(user_input, shell=True)
```

| 3 | Select Language: **Python** | |
| 4 | Click **Analyze** | Agent processes code |
| 5 | Check **Security** tab | Should flag hardcoded API key + command injection |
| 6 | Check **Performance** tab | Should flag nested O(n) loop |
| 7 | **Result** | Code analysis detects vulnerabilities |

### Test 6: Download Report

| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | After a review completes, scroll to bottom of results | Download buttons visible |
| 2 | Click **Download Report (MD)** | File `codesense_report_YYYYMMDD_HHMMSS.md` downloads |
| 3 | Click **Download JSON** | JSON version downloads |
| 4 | Open the MD file | Contains full review with score, issues, suggestions |
| 5 | **Result** | Report export works |

### Test 7: Review History

| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Run 2-3 reviews with different inputs | |
| 2 | Scroll below the results section | "Review History" section with data table |
| 3 | Table shows | Timestamp, Source, Score, Critical, Warnings, Files columns |
| 4 | **Result** | History tracking works |

### Test 8: Sidebar Controls

| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Check sidebar | Session stats show review count and average score |
| 2 | Toggle **API Status** refresh button | Shows Online/Offline indicator |
| 3 | Change **Model** dropdown | Model selection persists across reviews |
| 4 | Adjust **Review Depth** slider | Depth setting applied to next review |
| 5 | **Result** | Sidebar controls functional |

---

## Part 4: Verification Checklist

```
[ ] Backend starts without errors (uvicorn on :8000)
[ ] Frontend loads without errors (streamlit on :8501)
[ ] GET /health returns {"status": "ok"}
[ ] GET / returns service info
[ ] Swagger docs at /docs load properly
[ ] POST /api/review with GitHub URL returns results
[ ] POST /api/review with code_content returns results
[ ] GET /api/review/{id} returns stored review
[ ] GET /api/reviews/history returns list
[ ] Streamlit UI shows hero header and input tabs
[ ] GitHub URL input triggers analysis with progress animation
[ ] Direct code paste triggers analysis
[ ] Security issues detected (hardcoded keys, command injection)
[ ] Performance issues flagged (nested loops)
[ ] Quality score displayed (0-100 scale)
[ ] Results render in 4 tabs
[ ] Download Markdown button works
[ ] Download JSON button works
[ ] Review history table populates
[ ] Sidebar shows session stats
[ ] API health check button works
[ ] Model selector and depth slider work
[ ] No console errors in backend or frontend terminals
[ ] pytest passes all 257 tests
```

---

## Part 5: Troubleshooting

| Error | Cause | Fix |
|-------|-------|-----|
| `Connection refused` on :8000/health | Backend not running | Check terminal 1 for errors; restart with `python -m uvicorn backend.main:app --reload` |
| `Unable to connect` to :8501 | Frontend not running | Check terminal 2; restart with `streamlit run frontend/streamlit_app.py` |
| `ModuleNotFoundError` | Dependencies missing | Run `pip install -r requirements.txt` |
| `API key invalid` during review | .env not configured | Check `.env` has `GEMINI_API_KEY` or `OPENAI_API_KEY` set |
| Review returns empty/demo results | Backend not connected | Frontend falls back to mock data; verify backend is running at :8000 |
| `Timeout waiting for results` | Agent taking too long | Try simpler code first; check backend logs for errors |
| `Address already in use` | Port already occupied | Kill existing process: `Stop-Process -Id (Get-NetTCPConnection -LocalPort 8000).OwningProcess` |
| `Streamlit command not found` | Package not installed | Run `pip install streamlit` |

---

## Part 6: Quick Test Script

Save as `test_agent.ps1` and run in PowerShell:

```powershell
Write-Host "Testing Code Review Agent..." -ForegroundColor Cyan

# Test 1: API health
try {
    $health = Invoke-RestMethod -Uri "http://localhost:8000/health" -ErrorAction Stop
    if ($health.status -eq "ok") { Write-Host "API Health: OK" -ForegroundColor Green }
} catch { Write-Host "API Health: FAILED (backend not running?)" -ForegroundColor Red }

# Test 2: API docs
try {
    $docs = Invoke-WebRequest -Uri "http://localhost:8000/docs" -ErrorAction Stop
    if ($docs.Content -match "Swagger") { Write-Host "API Docs: OK" -ForegroundColor Green }
} catch { Write-Host "API Docs: FAILED" -ForegroundColor Red }

# Test 3: Python imports
try {
    python -c "from agent.agent import CodeReviewAgent; print('Agent imports: OK')"
} catch { Write-Host "Agent imports: FAILED" -ForegroundColor Red }

Write-Host "`nOpen http://localhost:8501 in browser to test the UI." -ForegroundColor Cyan
```

Or run individual checks from PowerShell directly:

```powershell
# Quick health check
curl http://localhost:8000/health

# Quick review test
$body = @{github_url="https://github.com/torvalds/linux"} | ConvertTo-Json
Invoke-RestMethod -Uri "http://localhost:8000/api/review" -Method Post -Body $body -ContentType "application/json"
```

---

## Part 7: Expected Results

### When Everything Works

```
Terminal 1 (Backend):
  INFO:     Application startup complete.
  INFO:     Uvicorn running on http://0.0.0.0:8000
  
Terminal 2 (Frontend):
  Local URL: http://localhost:8501
  
Browser:
  http://localhost:8000/health   -> {"status":"ok","message":"Server is running"}
  http://localhost:8000/docs     -> Swagger UI with 4 endpoints
  http://localhost:8501          -> CodeSense AI UI with hero header
  
API Review Response:
  {
    "status": "success",
    "review_id": "uuid-here",
    "quality_score": 7.5,
    "total_issues": 5,
    "critical_issues": 2,
    "security_issues": 1,
    "performance_issues": 1,
    "issues": [...],
    "report": "...",
    "timestamp": "2025-01-..."
  }
```

---

## Part 8: Final Summary

After completing all tests, fill this in:

| Check | Status |
|-------|--------|
| Backend starts | / |
| Frontend starts | / |
| API health endpoint | / |
| API docs (Swagger) | / |
| POST /api/review (GitHub) | / |
| POST /api/review (code) | / |
| GET review by ID | / |
| Review history | / |
| Security detection | / |
| Performance detection | / |
| Download report | / |
| UI sidebar controls | / |
| 257 tests pass | / |
| **Overall Status** | **Working / Partially / Not Working** |

### Score: /10

### Issues Found:
- (list any)

### Next Steps:
- (list any fixes needed)
