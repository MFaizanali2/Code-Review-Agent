"""
Code Review Agent - Premium Streamlit Frontend
Person 5: Frontend + DevOps
"""

import streamlit as st
import json
import pandas as pd
from datetime import datetime
import time
from api_client import APIClient


# ─── UI Helper Functions ──────────────────────────────────────────────────────

def _section_header(icon: str, title: str, extra_style: str = "") -> None:
    """Render a consistent section header."""
    st.markdown(f"""
    <div class="section-header"{extra_style}>
        <div class="section-icon">{icon}</div>
        <div class="section-title">{title}</div>
    </div>
    """, unsafe_allow_html=True)


def _render_issue_card(issue: dict, sev_map: dict) -> None:
    """Render a single issue card."""
    sev = issue.get("severity", "info")
    pill_class, icon = sev_map.get(sev, ("pill-info", "🔵"))
    st.markdown(f"""
    <div class="issue-card {'danger' if sev=='critical' else sev}">
        <div style="display:flex; justify-content:space-between; align-items:flex-start">
            <div class="issue-title">{icon} {issue['title']}</div>
            <span class="status-pill {pill_class}">{sev}</span>
        </div>
        <div class="issue-desc">{issue['desc']}</div>
        <div class="issue-line">📍 {issue.get('line','—')}</div>
    </div>
    """, unsafe_allow_html=True)


def _render_quality_metric(name: str, val: int) -> None:
    """Render a single quality metric with colored progress bar."""
    color = "#00E676" if val >= 80 else "#FFD600" if val >= 60 else "#FF4C4C"
    st.markdown(f"**{name.replace('_',' ').title()}**")
    st.progress(val / 100)
    st.markdown(
        f"<div style='color:{color}; font-family: Space Mono; "
        f"font-size:0.8rem; margin-top:-12px; margin-bottom:12px'>{val}/100</div>",
        unsafe_allow_html=True,
    )


def _build_history_entry(h: dict) -> dict:
    """Build a history table row from a result dict."""
    return {
        "Timestamp": h.get("timestamp", "—"),
        "Source": h.get("source", "—")[:50],
        "Score": f"{h.get('overall_score', '—')}/100",
        "Critical": h.get("critical_issues", 0),
        "Warnings": h.get("warnings", 0),
        "Files": h.get("files_analyzed", 0),
    }


# ─── Page Configuration ──────────────────────────────────────────────────────
st.set_page_config(
    page_title="CodeSense AI — Intelligent Code Review",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        "Get Help": "https://github.com/your-repo",
        "Report a bug": "https://github.com/your-repo/issues",
        "About": "CodeSense AI — Powered by Gemini + FastAPI"
    }
)

# ─── Custom CSS (Premium Dark Theme) ─────────────────────────────────────────
st.markdown("""
<style>
/* Import Fonts */
@import url('https://fonts.googleapis.com/css2?family=Space+Mono:wght@400;700&family=DM+Sans:wght@300;400;500;600;700&display=swap');

/* Root Variables */
:root {
    --primary: #6C63FF;
    --primary-glow: rgba(108, 99, 255, 0.3);
    --accent: #00D2FF;
    --success: #00E676;
    --warning: #FFD600;
    --danger: #FF4C4C;
    --bg-dark: #0A0A0F;
    --bg-card: #13131A;
    --bg-card2: #1A1A24;
    --border: rgba(108, 99, 255, 0.2);
    --text-primary: #F0F0FF;
    --text-secondary: #8888AA;
    --font-mono: 'Space Mono', monospace;
    --font-body: 'DM Sans', sans-serif;
}

/* Global Reset */
.stApp {
    background: var(--bg-dark);
    font-family: var(--font-body);
    color: var(--text-primary);
}

/* Hide Streamlit Branding */
#MainMenu, footer, header { visibility: hidden; }
.stDeployButton { display: none; }

/* Sidebar */
[data-testid="stSidebar"] {
    background: var(--bg-card) !important;
    border-right: 1px solid var(--border);
}

[data-testid="stSidebar"] .stMarkdown h1,
[data-testid="stSidebar"] .stMarkdown h2,
[data-testid="stSidebar"] .stMarkdown h3 {
    color: var(--text-primary);
}

/* Hero Header */
.hero-header {
    text-align: center;
    padding: 3rem 2rem 2rem;
    position: relative;
}

.hero-header::before {
    content: '';
    position: absolute;
    top: 0; left: 50%;
    transform: translateX(-50%);
    width: 600px; height: 200px;
    background: radial-gradient(ellipse, var(--primary-glow), transparent 70%);
    pointer-events: none;
}

.hero-badge {
    display: inline-block;
    background: linear-gradient(135deg, var(--primary), var(--accent));
    color: white;
    font-family: var(--font-mono);
    font-size: 0.7rem;
    padding: 4px 16px;
    border-radius: 50px;
    letter-spacing: 3px;
    text-transform: uppercase;
    margin-bottom: 1rem;
}

.hero-title {
    font-family: var(--font-body);
    font-size: 3.5rem;
    font-weight: 700;
    letter-spacing: -2px;
    line-height: 1;
    margin: 0.5rem 0;
    background: linear-gradient(135deg, #FFFFFF 30%, var(--accent));
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
}

.hero-subtitle {
    color: var(--text-secondary);
    font-size: 1.1rem;
    font-weight: 300;
    margin-top: 0.5rem;
    letter-spacing: 0.5px;
}

/* Cards */
.metric-card {
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: 16px;
    padding: 1.5rem;
    text-align: center;
    transition: all 0.3s ease;
    position: relative;
    overflow: hidden;
}

.metric-card::after {
    content: '';
    position: absolute;
    top: 0; left: 0; right: 0;
    height: 2px;
    background: linear-gradient(90deg, var(--primary), var(--accent));
}

.metric-value {
    font-family: var(--font-mono);
    font-size: 2.5rem;
    font-weight: 700;
    color: var(--accent);
}

.metric-label {
    color: var(--text-secondary);
    font-size: 0.8rem;
    text-transform: uppercase;
    letter-spacing: 2px;
    margin-top: 4px;
}

/* Score Ring */
.score-display {
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: 20px;
    padding: 2rem;
    text-align: center;
}

/* Issue Cards */
.issue-card {
    background: var(--bg-card2);
    border-radius: 12px;
    padding: 1rem 1.25rem;
    margin: 0.5rem 0;
    border-left: 3px solid var(--danger);
    font-family: var(--font-body);
}

.issue-card.warning { border-left-color: var(--warning); }
.issue-card.success { border-left-color: var(--success); }
.issue-card.info    { border-left-color: var(--primary); }

.issue-title {
    font-weight: 600;
    font-size: 0.9rem;
    color: var(--text-primary);
}

.issue-desc {
    color: var(--text-secondary);
    font-size: 0.82rem;
    margin-top: 4px;
}

.issue-line {
    font-family: var(--font-mono);
    font-size: 0.72rem;
    color: var(--accent);
    margin-top: 6px;
}

/* Section Headers */
.section-header {
    display: flex;
    align-items: center;
    gap: 12px;
    margin: 2rem 0 1rem;
    padding-bottom: 12px;
    border-bottom: 1px solid var(--border);
}

.section-icon {
    width: 36px; height: 36px;
    background: var(--primary-glow);
    border-radius: 10px;
    display: flex; align-items: center; justify-content: center;
    font-size: 1rem;
}

.section-title {
    font-size: 1.1rem;
    font-weight: 600;
    color: var(--text-primary);
}

/* Code Block */
.code-preview {
    background: #0D0D14;
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 1rem 1.25rem;
    font-family: var(--font-mono);
    font-size: 0.78rem;
    color: #A8B2D8;
    overflow-x: auto;
    max-height: 200px;
    overflow-y: auto;
}

/* Status Pills */
.status-pill {
    display: inline-block;
    padding: 3px 12px;
    border-radius: 50px;
    font-size: 0.72rem;
    font-weight: 600;
    font-family: var(--font-mono);
    text-transform: uppercase;
    letter-spacing: 1px;
}

.pill-critical { background: rgba(255,76,76,0.15); color: #FF4C4C; border: 1px solid rgba(255,76,76,0.3); }
.pill-warning  { background: rgba(255,214,0,0.12); color: #FFD600; border: 1px solid rgba(255,214,0,0.3); }
.pill-good     { background: rgba(0,230,118,0.12); color: #00E676; border: 1px solid rgba(0,230,118,0.3); }
.pill-info     { background: rgba(108,99,255,0.15); color: #9D95FF; border: 1px solid rgba(108,99,255,0.3); }

/* Input Styling */
.stTextInput input, .stTextArea textarea {
    background: var(--bg-card) !important;
    border: 1px solid var(--border) !important;
    border-radius: 10px !important;
    color: var(--text-primary) !important;
    font-family: var(--font-body) !important;
}

.stTextInput input:focus, .stTextArea textarea:focus {
    border-color: var(--primary) !important;
    box-shadow: 0 0 0 3px var(--primary-glow) !important;
}

/* Buttons */
.stButton > button {
    background: linear-gradient(135deg, var(--primary), #8B7FFF) !important;
    color: white !important;
    border: none !important;
    border-radius: 10px !important;
    padding: 0.6rem 2rem !important;
    font-family: var(--font-body) !important;
    font-weight: 600 !important;
    font-size: 0.95rem !important;
    letter-spacing: 0.5px !important;
    transition: all 0.3s ease !important;
    box-shadow: 0 4px 24px var(--primary-glow) !important;
}

.stButton > button:hover {
    transform: translateY(-2px) !important;
    box-shadow: 0 8px 32px var(--primary-glow) !important;
}

/* Tab Styling */
.stTabs [data-baseweb="tab-list"] {
    background: var(--bg-card) !important;
    border-radius: 12px !important;
    padding: 4px !important;
    gap: 4px !important;
    border: 1px solid var(--border) !important;
}

.stTabs [data-baseweb="tab"] {
    background: transparent !important;
    border-radius: 8px !important;
    color: var(--text-secondary) !important;
    font-weight: 500 !important;
}

.stTabs [aria-selected="true"] {
    background: var(--primary) !important;
    color: white !important;
}

/* Progress Bar */
.stProgress > div > div {
    background: linear-gradient(90deg, var(--primary), var(--accent)) !important;
    border-radius: 4px !important;
}

/* DataFrame */
.stDataFrame {
    border: 1px solid var(--border) !important;
    border-radius: 12px !important;
    overflow: hidden !important;
}

/* Expander */
.streamlit-expanderHeader {
    background: var(--bg-card2) !important;
    border: 1px solid var(--border) !important;
    border-radius: 10px !important;
    color: var(--text-primary) !important;
}

/* Scrollbar */
::-webkit-scrollbar { width: 4px; height: 4px; }
::-webkit-scrollbar-track { background: var(--bg-dark); }
::-webkit-scrollbar-thumb { background: var(--primary); border-radius: 4px; }

/* Loading Animation */
@keyframes pulse-glow {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.5; }
}

.analyzing-text {
    animation: pulse-glow 1.5s ease-in-out infinite;
    color: var(--accent);
    font-family: var(--font-mono);
    font-size: 0.85rem;
}

/* Footer */
.custom-footer {
    text-align: center;
    padding: 2rem;
    color: var(--text-secondary);
    font-size: 0.75rem;
    font-family: var(--font-mono);
    border-top: 1px solid var(--border);
    margin-top: 4rem;
}
</style>
""", unsafe_allow_html=True)

# ─── Session State Init ───────────────────────────────────────────────────────
if "api_endpoint" not in st.session_state:
    st.session_state.api_endpoint = "http://localhost:8000"
if "review_result" not in st.session_state:
    st.session_state.review_result = None
if "analyzing" not in st.session_state:
    st.session_state.analyzing = False
if "history" not in st.session_state:
    st.session_state.history = []

# ─── API Client ───────────────────────────────────────────────────────────────
api = APIClient(st.session_state.api_endpoint)

# ─── Sidebar ──────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("""
    <div style="text-align:center; padding: 1rem 0 1.5rem;">
        <div style="font-size: 2.5rem; margin-bottom: 8px;">🧠</div>
        <div style="font-family: 'Space Mono', monospace; font-weight: 700; font-size: 1.1rem; color: #F0F0FF;">CodeSense AI</div>
        <div style="font-size: 0.75rem; color: #8888AA; margin-top: 4px;">v1.0 · Agent-Powered</div>
    </div>
    """, unsafe_allow_html=True)

    st.divider()

    # API Settings
    st.markdown("**⚙️ API Configuration**")
    endpoint = st.text_input(
        "Backend Endpoint",
        value=st.session_state.api_endpoint,
        key="endpoint_input",
        label_visibility="collapsed",
        placeholder="http://localhost:8000"
    )
    if endpoint != st.session_state.api_endpoint:
        st.session_state.api_endpoint = endpoint
        api = APIClient(endpoint)

    # Health Check
    col_h1, col_h2 = st.columns([3, 1])
    with col_h1:
        st.markdown("**API Status**")
    with col_h2:
        if st.button("🔄", help="Check API health"):
            health = api.health_check()
            if health:
                st.success("Online")
            else:
                st.error("Offline")

    st.divider()

    # Model Selection
    st.markdown("**🤖 Model**")
    model = st.selectbox(
        "LLM Model",
        ["gemini-2.0-flash", "gemini-1.5-pro", "gpt-4o", "claude-3-5-sonnet"],
        label_visibility="collapsed"
    )

    # Review Depth
    st.markdown("**📊 Review Depth**")
    depth = st.select_slider(
        "Depth",
        options=["Quick", "Standard", "Deep", "Comprehensive"],
        value="Standard",
        label_visibility="collapsed"
    )

    st.divider()

    # Stats
    st.markdown("**📈 Session Stats**")
    col_s1, col_s2 = st.columns(2)
    with col_s1:
        st.markdown(f"""
        <div class="metric-card" style="padding:1rem">
            <div class="metric-value" style="font-size:1.8rem">{len(st.session_state.history)}</div>
            <div class="metric-label">Reviews</div>
        </div>
        """, unsafe_allow_html=True)
    with col_s2:
        avg_score = 0
        if st.session_state.history:
            scores = [r.get("overall_score", 0) for r in st.session_state.history if r.get("overall_score")]
            avg_score = int(sum(scores) / len(scores)) if scores else 0
        st.markdown(f"""
        <div class="metric-card" style="padding:1rem">
            <div class="metric-value" style="font-size:1.8rem">{avg_score}</div>
            <div class="metric-label">Avg Score</div>
        </div>
        """, unsafe_allow_html=True)

    st.divider()
    st.markdown("""
    <div style="font-size:0.72rem; color:#8888AA; font-family:'Space Mono',monospace; text-align:center; line-height:2">
    Built by <span style="color:#6C63FF">Person 5</span><br>
    Frontend + DevOps<br>
    Agentic AI Course
    </div>
    """, unsafe_allow_html=True)

# ─── Hero Header ──────────────────────────────────────────────────────────────
st.markdown("""
<div class="hero-header">
    <div class="hero-badge">✦ AI-Powered Code Intelligence</div>
    <div class="hero-title">CodeSense AI</div>
    <div class="hero-subtitle">Analyze. Detect. Improve. — Powered by ReACT Agent + Gemini</div>
</div>
""", unsafe_allow_html=True)

# ─── Input Section ────────────────────────────────────────────────────────────
_section_header("📥", "Submit Code for Review")

input_tab1, input_tab2 = st.tabs(["🔗  GitHub Repository", "📋  Paste Code"])

with input_tab1:
    col_url, col_btn = st.columns([5, 1])
    with col_url:
        github_url = st.text_input(
            "Repository URL",
            placeholder="https://github.com/username/repository",
            label_visibility="collapsed",
            key="github_url"
        )
    with col_btn:
        st.markdown("<br>", unsafe_allow_html=True)
        analyze_github = st.button("Analyze →", key="btn_github", use_container_width=True)

    if github_url:
        st.markdown(f"""
        <div class="issue-card info" style="margin-top:0.5rem">
            <div class="issue-title">📦 Repository Detected</div>
            <div class="issue-desc">{github_url}</div>
        </div>
        """, unsafe_allow_html=True)

with input_tab2:
    code_content = st.text_area(
        "Paste your code here",
        placeholder="# Paste your Python, JavaScript, Java, or any code here...\n\ndef example():\n    pass",
        height=200,
        label_visibility="collapsed",
        key="code_input"
    )

    col_lang, col_btn2 = st.columns([3, 1])
    with col_lang:
        lang = st.selectbox(
            "Language",
            ["Python", "JavaScript", "TypeScript", "Java", "Go", "Rust", "C++", "C#", "Auto-detect"],
            label_visibility="collapsed"
        )
    with col_btn2:
        analyze_code = st.button("Analyze →", key="btn_code", use_container_width=True)

# ─── Analysis Logic ───────────────────────────────────────────────────────────
trigger_analysis = False
analysis_payload = {}

if analyze_github and github_url:
    trigger_analysis = True
    analysis_payload = {"github_url": github_url, "model": model, "depth": depth}
elif analyze_code and code_content:
    trigger_analysis = True
    analysis_payload = {"code_content": code_content, "language": lang, "model": model, "depth": depth}

if trigger_analysis:
    with st.spinner(""):
        # Progress animation
        progress_placeholder = st.empty()
        progress_placeholder.markdown("""
        <div style="text-align:center; padding: 2rem; background: #13131A; border-radius: 16px; border: 1px solid rgba(108,99,255,0.2); margin: 1rem 0">
            <div style="font-size: 2rem; margin-bottom: 12px;">🤖</div>
            <div class="analyzing-text">AGENT ANALYZING CODE...</div>
            <div style="color: #8888AA; font-size: 0.78rem; margin-top: 8px; font-family: 'Space Mono', monospace">
                ReACT Loop Running · Gemini Processing
            </div>
        </div>
        """, unsafe_allow_html=True)

        # Simulate agent steps in progress bar
        steps = ["🔍 Fetching repository...", "🧬 Parsing code structure...", "🛡️ Running security scan...", "⚡ Checking performance...", "📊 Generating report..."]
        step_bar = st.empty()
        for i, step in enumerate(steps):
            step_bar.markdown(f"""
            <div style="color: #6C63FF; font-family: 'Space Mono', monospace; font-size: 0.78rem; padding: 6px 0">
                {step}
            </div>
            """, unsafe_allow_html=True)
            time.sleep(0.4)
        step_bar.empty()

        # Real API call
        result = api.review_code(
            github_url=analysis_payload.get("github_url"),
            code_content=analysis_payload.get("code_content"),
            model=model,
            depth=depth
        )

        progress_placeholder.empty()

        if result and result.get("status") == "success":
            st.session_state.review_result = result
            st.session_state.history.append({
                **result,
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
                "source": github_url if github_url else "Pasted Code"
            })
            st.success("✅ Analysis complete!")
        else:
            # Demo mode with mock data
            mock_result = api.get_mock_result(analysis_payload)
            st.session_state.review_result = mock_result
            st.session_state.history.append({
                **mock_result,
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
                "source": analysis_payload.get("github_url", "Pasted Code")
            })
            st.info("📡 Running in Demo Mode — connect backend for live analysis")

# ─── Results Section ──────────────────────────────────────────────────────────
if st.session_state.review_result:
    result = st.session_state.review_result

    _section_header("📊", "Review Results")

    # Score Overview
    score = result.get("overall_score", 72)
    issues_critical = result.get("critical_issues", 3)
    issues_warning = result.get("warnings", 7)
    files_analyzed = result.get("files_analyzed", 12)
    lines_analyzed = result.get("lines_of_code", 845)

    col1, col2, col3, col4, col5 = st.columns(5)
    metrics = [
        (score, "Overall Score", "accent"),
        (files_analyzed, "Files Analyzed", "accent"),
        (lines_analyzed, "Lines of Code", "accent"),
        (issues_critical, "Critical Issues", "#FF4C4C"),
        (issues_warning, "Warnings", "#FFD600"),
    ]
    for col, (val, label, color) in zip([col1, col2, col3, col4, col5], metrics):
        with col:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-value" style="color:{color}">{val}</div>
                <div class="metric-label">{label}</div>
            </div>
            """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # Tabs for results
    r_tab1, r_tab2, r_tab3, r_tab4 = st.tabs(["🛡️  Security", "⚡  Performance", "🏗️  Code Quality", "📋  Full Report"])

    with r_tab1:
        security_issues = result.get("security_issues", [
            {"title": "SQL Injection Risk", "severity": "critical", "line": "Line 47", "desc": "User input directly concatenated into SQL query without sanitization."},
            {"title": "Hardcoded API Key", "severity": "critical", "line": "Line 12", "desc": "API key found in source code. Move to environment variables."},
            {"title": "Weak Password Hashing", "severity": "warning", "line": "Line 89", "desc": "MD5 used for password hashing. Use bcrypt or argon2 instead."},
            {"title": "Missing CSRF Protection", "severity": "warning", "line": "Line 156", "desc": "POST endpoints lack CSRF token validation."},
            {"title": "Dependencies Up to Date", "severity": "good", "line": "All", "desc": "No known vulnerabilities in listed dependencies."},
        ])

        sev_map = {"critical": ("pill-critical", "🔴"), "warning": ("pill-warning", "🟡"), "good": ("pill-good", "🟢"), "info": ("pill-info", "🔵")}

        for issue in security_issues:
            _render_issue_card(issue, sev_map)

    with r_tab2:
        perf_issues = result.get("performance_issues", [
            {"title": "N+1 Query Pattern Detected", "severity": "critical", "line": "Line 203-215", "desc": "Database query inside loop causes N+1 problem. Use batch query instead."},
            {"title": "Inefficient List Comprehension", "severity": "warning", "line": "Line 78", "desc": "Nested list comprehension O(n²). Consider using sets or dicts."},
            {"title": "Missing Caching on API Calls", "severity": "warning", "line": "Lines 301-320", "desc": "Expensive external API called on every request. Add Redis caching."},
            {"title": "Async Functions Used Correctly", "severity": "good", "line": "All async", "desc": "Async/await patterns are properly implemented throughout."},
        ])

        for issue in perf_issues:
            _render_issue_card(issue, sev_map)

    with r_tab3:
        col_q1, col_q2 = st.columns(2)
        quality = result.get("quality_metrics", {
            "maintainability": 78, "readability": 65, "test_coverage": 42,
            "documentation": 55, "complexity": 71, "modularity": 88
        })

        with col_q1:
            for metric, val in list(quality.items())[:3]:
                _render_quality_metric(metric, val)

        with col_q2:
            for metric, val in list(quality.items())[3:]:
                _render_quality_metric(metric, val)

        # Suggestions
        st.markdown("#### 💡 AI Suggestions")
        suggestions = result.get("suggestions", [
            "Add docstrings to all public functions and classes",
            "Increase unit test coverage to at least 80%",
            "Extract repeated logic into utility functions",
            "Use type hints consistently across all modules",
            "Consider splitting large files (>300 lines) into modules"
        ])
        for s in suggestions:
            st.markdown(f"""
            <div class="issue-card info" style="padding: 0.75rem 1rem">
                <div class="issue-desc">✦ {s}</div>
            </div>
            """, unsafe_allow_html=True)

    with r_tab4:
        # Full report
        report_md = result.get("full_report", f"""
## 🧠 CodeSense AI — Code Review Report

**Generated:** {datetime.now().strftime('%B %d, %Y at %H:%M')}
**Model:** {model} | **Depth:** {depth}

---

### Overall Score: {score}/100

Your codebase shows **moderate quality** with some critical security issues that need immediate attention.

### Critical Actions Required
1. Fix SQL injection vulnerability on Line 47
2. Remove hardcoded API key from source code
3. Address N+1 query pattern in data fetching layer

### Strengths
- Good use of async/await patterns
- Modular architecture with clear separation of concerns
- Dependencies are up to date with no known vulnerabilities

### Summary
- **{files_analyzed}** files analyzed across the repository
- **{lines_analyzed}** total lines of code reviewed
- **{issues_critical}** critical issues found requiring immediate fix
- **{issues_warning}** warnings to address in next iteration
        """)

        st.markdown(report_md)

        # Download buttons
        st.markdown("<br>", unsafe_allow_html=True)
        dl_col1, dl_col2, dl_col3 = st.columns(3)
        ts = datetime.now().strftime("%Y%m%d_%H%M")

        with dl_col1:
            st.download_button(
                "⬇️ Download Report (MD)",
                data=report_md,
                file_name=f"codesense_report_{ts}.md",
                mime="text/markdown",
                use_container_width=True
            )
        with dl_col2:
            json_data = json.dumps(result, indent=2, default=str)
            st.download_button(
                "⬇️ Download JSON",
                data=json_data,
                file_name=f"codesense_report_{ts}.json",
                mime="application/json",
                use_container_width=True
            )
        with dl_col3:
            if st.button("🔄 New Analysis", use_container_width=True):
                st.session_state.review_result = None
                st.rerun()

# ─── History Section ──────────────────────────────────────────────────────────
if st.session_state.history:
    _section_header("📜", "Review History", extra_style=' style="margin-top: 3rem"')

    history_data = [_build_history_entry(h) for h in reversed(st.session_state.history)]

    df = pd.DataFrame(history_data)
    st.dataframe(df, use_container_width=True, hide_index=True)

    if st.button("🗑️ Clear History"):
        st.session_state.history = []
        st.rerun()

# ─── Footer ───────────────────────────────────────────────────────────────────
st.markdown("""
<div class="custom-footer">
    CodeSense AI · Built with Streamlit + FastAPI + Gemini<br>
    <span style="color:#6C63FF">Person 5 · Frontend & DevOps · Agentic AI Course 2025</span>
</div>
""", unsafe_allow_html=True)