# 🔍 Code Review Agent - 5 Member Team Roles

**Project:** AI-Powered Code Review Agent using FastAPI + Gemini + Streamlit  
**Team Size:** 5 Members  
**Duration:** 2 Weeks  
**Technology Stack:** Python, FastAPI, Streamlit, Gemini/OpenAI, Git

---

## 📌 Project Overview

**Kya Banayenge?**
- GitHub repository links analyze karega
- Code quality check karega
- Security vulnerabilities detect karega
- Performance issues identify karega
- Detailed review report generate karega
- Beautiful Streamlit UI se results display karega

**Tech Stack:**
```
Backend: FastAPI + Python
LLM: Gemini 2.0 Flash / OpenAI
Tools: AST Parser, GitHub API, Bandit, Pylint
Frontend: Streamlit
Database: SQLite
```

---

## 👥 Team Member Roles (Detailed)

---

## 👤 Person 1: "Agent Architect" (Team Lead)

### **Primary Role**
Agent ka dimaagh - ReACT loop design karna, decision-making logic implement karna, tool orchestration manage karna

### **Responsibilities**

| Task | Details |
|------|---------|
| **ReACT Loop Design** | Think → Act → Observe → Reflect cycle design karna |
| **Agent State Management** | Agent ka state track karna, memory manage karna |
| **Error Handling** | Failed tools, retries, fallbacks implement karna |
| **Tool Selection Logic** | Agent soche ke konsa tool use karna chahiye |
| **Integration Hub** | Sab modules ko ek saath kaise kaam karega plan karna |

### **Code Responsibilities**

```python
Files to Create:
├── agent/
│   ├── agent_core.py          ← Main agent class
│   ├── agent_memory.py         ← Conversation history
│   ├── agent_orchestrator.py   ← Tool coordination
│   ├── agent_types.py          ← Type definitions
│   └── __init__.py
```

### **Detailed Code Tasks**

```python
# 1. Agent Core Loop
class CodeReviewAgent:
    def __init__(self, llm_client, tools):
        self.llm = llm_client
        self.tools = tools
        self.memory = []
        
    async def run(self, user_query):
        """Main ReACT loop"""
        step = 0
        max_steps = 10
        
        while step < max_steps:
            # THINK: Plan next action
            action_plan = await self.think(user_query)
            
            # ACT: Execute tool
            result = await self.act(action_plan)
            
            # OBSERVE: Check result
            observation = await self.observe(result)
            
            # REFLECT: Update state
            await self.reflect(observation)
            
            step += 1
        
        return self.memory

# 2. Memory Management
class AgentMemory:
    def __init__(self):
        self.conversation_history = []
        self.tool_results = {}
        
    def add_step(self, step_type, content):
        """Log har step"""
        pass
    
    def get_context(self):
        """LLM ke liye context prepare karo"""
        pass

# 3. Tool Orchestrator
class ToolOrchestrator:
    def __init__(self, tools):
        self.tools = tools
        self.tool_results = {}
    
    async def execute_tool(self, tool_name, params):
        """Tool execute karo aur result store karo"""
        pass
    
    async def parallel_tools(self, tools_list):
        """Multiple tools ko ek saath chalao"""
        pass
```

### **Deliverables**
- ✅ `agent_core.py` - Agent class
- ✅ `agent_memory.py` - Memory system
- ✅ `agent_orchestrator.py` - Tool execution
- ✅ `AGENT_ARCHITECTURE.md` - Design documentation
- ✅ `test_agent_loop.py` - Unit tests

### **Dependencies**
- Depends on: Person 2 (Tools), Person 3 (LLM)
- Required by: Person 4 (FastAPI)

### **Meeting Points**
- Daily 10 AM: Sync with Person 2 & 3
- Wednesday: Integration testing with Person 4

### **Success Criteria**
- [ ] ReACT loop 10 steps tak chale
- [ ] Memory properly maintain ho
- [ ] Tools synchronously execute ho
- [ ] Error handling graceful ho

---

## 👤 Person 2: "Tool Engineer"

### **Primary Role**
Sab tools implement karna jo agent use karega. Tools actual work karti hain!

### **Responsibilities**

| Tool | Function | Complexity |
|------|----------|-----------|
| **GitHub Tool** | Repo clone, file list | Easy |
| **Code Analyzer** | Structure, imports, functions | Medium |
| **Security Checker** | Vulnerabilities detect | Hard |
| **Performance Analyzer** | Inefficiencies find | Hard |
| **Report Generator** | Summary create | Medium |

### **Code Responsibilities**

```python
Files to Create:
├── tools/
│   ├── __init__.py
│   ├── base_tool.py           ← Tool ka template
│   ├── github_tool.py         ← Git operations
│   ├── code_analyzer.py       ← AST analysis
│   ├── security_checker.py    ← Vulnerability scan
│   ├── performance_checker.py ← Performance issues
│   ├── report_generator.py    ← Summary report
│   └── utils.py               ← Helper functions
```

### **Detailed Code Tasks**

#### **1. Base Tool Template**
```python
# tools/base_tool.py
from abc import ABC, abstractmethod

class BaseTool(ABC):
    def __init__(self, name: str, description: str):
        self.name = name
        self.description = description
    
    @abstractmethod
    async def execute(self, **kwargs):
        """Tool ko execute karo"""
        pass
    
    def to_schema(self):
        """LLM ke liye tool definition"""
        pass
```

#### **2. GitHub Tool**
```python
# tools/github_tool.py
from git import Repo
import os

class GitHubTool(BaseTool):
    def __init__(self):
        super().__init__(
            name="fetch_repository",
            description="GitHub se code download karo"
        )
    
    async def execute(self, github_url: str, target_dir: str = "./temp_repo"):
        """
        Repository clone karo
        """
        try:
            repo = Repo.clone_from(github_url, target_dir)
            files = self.get_all_files(target_dir)
            languages = self.detect_languages(target_dir)
            
            return {
                "status": "success",
                "repo_path": target_dir,
                "file_count": len(files),
                "languages": languages,
                "files": files
            }
        except Exception as e:
            return {
                "status": "error",
                "message": str(e)
            }
    
    def get_all_files(self, path):
        """Sab files get karo"""
        files = []
        for root, dirs, filenames in os.walk(path):
            for file in filenames:
                files.append(os.path.join(root, file))
        return files
    
    def detect_languages(self, path):
        """Language detect karo (Python, JS, Java, etc)"""
        extensions = {}
        for root, dirs, files in os.walk(path):
            for file in files:
                ext = os.path.splitext(file)[1]
                extensions[ext] = extensions.get(ext, 0) + 1
        return extensions
```

#### **3. Code Analyzer**
```python
# tools/code_analyzer.py
import ast
import os

class CodeAnalyzerTool(BaseTool):
    def __init__(self):
        super().__init__(
            name="analyze_code_structure",
            description="Code ka structure nikalo"
        )
    
    async def execute(self, code_path: str):
        """
        Code analyze karo
        """
        analysis = {
            "functions": [],
            "classes": [],
            "imports": [],
            "lines_of_code": 0,
            "complexity": 0
        }
        
        try:
            with open(code_path, 'r') as f:
                code = f.read()
                tree = ast.parse(code)
            
            # Functions extract karo
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    analysis["functions"].append({
                        "name": node.name,
                        "line": node.lineno,
                        "args": len(node.args.args)
                    })
                elif isinstance(node, ast.ClassDef):
                    analysis["classes"].append({
                        "name": node.name,
                        "line": node.lineno,
                        "methods": len([n for n in node.body if isinstance(n, ast.FunctionDef)])
                    })
                elif isinstance(node, ast.Import) or isinstance(node, ast.ImportFrom):
                    analysis["imports"].append(ast.unparse(node))
            
            analysis["lines_of_code"] = len(code.split('\n'))
            analysis["complexity"] = self.calculate_complexity(tree)
            
            return {"status": "success", "data": analysis}
        except Exception as e:
            return {"status": "error", "message": str(e)}
    
    def calculate_complexity(self, tree):
        """Cyclomatic complexity calculate karo"""
        complexity = 1
        for node in ast.walk(tree):
            if isinstance(node, (ast.If, ast.While, ast.For, ast.ExceptHandler)):
                complexity += 1
        return complexity
```

#### **4. Security Checker**
```python
# tools/security_checker.py
import re

class SecurityCheckerTool(BaseTool):
    def __init__(self):
        super().__init__(
            name="security_audit",
            description="Security vulnerabilities check karo"
        )
    
    async def execute(self, code_path: str):
        """
        Security issues find karo
        """
        issues = []
        
        with open(code_path, 'r') as f:
            code = f.read()
        
        # Check 1: SQL Injection patterns
        if re.search(r"execute\s*\(\s*f['\"].*{.*}.*['\"]\)", code):
            issues.append({
                "type": "SQL Injection",
                "severity": "HIGH",
                "message": "F-string query building detected"
            })
        
        # Check 2: Hardcoded secrets
        if re.search(r"(password|api_key|secret)\s*=\s*['\"].*['\"]\)", code):
            issues.append({
                "type": "Hardcoded Secrets",
                "severity": "CRITICAL",
                "message": "Hardcoded credentials found"
            })
        
        # Check 3: Eval usage
        if "eval(" in code or "exec(" in code:
            issues.append({
                "type": "Code Execution",
                "severity": "CRITICAL",
                "message": "Unsafe eval/exec usage"
            })
        
        # Check 4: No input validation
        if "request.args" in code and ".get(" in code:
            issues.append({
                "type": "Input Validation",
                "severity": "MEDIUM",
                "message": "No input validation found"
            })
        
        return {"status": "success", "issues": issues}
```

#### **5. Performance Checker**
```python
# tools/performance_checker.py
import re

class PerformanceCheckerTool(BaseTool):
    def __init__(self):
        super().__init__(
            name="performance_analysis",
            description="Performance issues find karo"
        )
    
    async def execute(self, code_path: str):
        """
        Performance problems detect karo
        """
        issues = []
        
        with open(code_path, 'r') as f:
            code = f.read()
        
        # Check 1: Nested loops
        nested_loops = code.count("for ") > 1 and code.count("for ") > 2
        if nested_loops:
            issues.append({
                "type": "Nested Loops",
                "severity": "MEDIUM",
                "message": "Multiple nested loops detected - O(n²) complexity",
                "suggestion": "Consider using hashmap or set"
            })
        
        # Check 2: String concatenation in loop
        if re.search(r"for.*\n.*\+.*=", code):
            issues.append({
                "type": "String Concatenation",
                "severity": "MEDIUM",
                "message": "String concatenation in loop",
                "suggestion": "Use list.join() instead"
            })
        
        # Check 3: Large data structures
        if "list(" in code and "range(" in code:
            issues.append({
                "type": "Memory Usage",
                "severity": "LOW",
                "message": "Creating large list in memory",
                "suggestion": "Consider using generator"
            })
        
        return {"status": "success", "issues": issues}
```

### **Deliverables**
- ✅ `tools/base_tool.py` - Tool template
- ✅ `tools/github_tool.py` - GitHub operations
- ✅ `tools/code_analyzer.py` - Code analysis
- ✅ `tools/security_checker.py` - Security audit
- ✅ `tools/performance_checker.py` - Performance check
- ✅ `tools/report_generator.py` - Report creation
- ✅ `tools/utils.py` - Helpers
- ✅ `TOOLS_DOCUMENTATION.md` - Tool specs
- ✅ `test_tools.py` - Unit tests

### **Dependencies**
- Depends on: None
- Required by: Person 1 (Agent), Person 3 (Schemas)
- Libraries: `GitPython`, `ast`, `re`

### **Success Criteria**
- [ ] Sab 5 tools working ho
- [ ] Each tool return consistent format
- [ ] Error handling ho
- [ ] Performance good ho (repos 5MB tak)

---

## 👤 Person 3: "LLM Integration Specialist"

### **Primary Role**
Gemini/OpenAI ko agent se connect karna aur prompts optimize karna

### **Responsibilities**

| Area | Task |
|------|------|
| **LLM Client** | API calls + response parsing |
| **Tool Schemas** | Tools ko JSON format mein define karna |
| **Prompts** | System prompt, few-shot examples |
| **Token Optimization** | Cost + speed optimize karna |
| **Response Handling** | Tool use responses parse karna |

### **Code Responsibilities**

```python
Files to Create:
├── llm/
│   ├── __init__.py
│   ├── llm_client.py          ← LLM API client
│   ├── llm_types.py           ← Type definitions
│   ├── prompts.py             ← System prompts
│   ├── tool_schemas.py        ← Tool definitions
│   └── response_parser.py     ← Parse LLM responses
```

### **Detailed Code Tasks**

#### **1. LLM Client**
```python
# llm/llm_client.py
from google import generativeai as genai
# OR from openai import OpenAI
import json

class LLMClient:
    def __init__(self, api_key: str, model: str = "gemini-2.0-flash"):
        self.api_key = api_key
        self.model = model
        
        # Gemini setup
        genai.configure(api_key=api_key)
        self.client = genai.GenerativeModel(model)
        
        # OR OpenAI setup
        # self.client = OpenAI(api_key=api_key)
    
    async def call_with_tools(self, messages: list, tools: list):
        """
        LLM ko call karo with tool definitions
        """
        try:
            response = self.client.generate_content(
                contents=messages,
                tools=tools,
                temperature=0.3,  # Consistent output
                top_p=0.9,
                top_k=40,
                max_output_tokens=1000
            )
            
            return {
                "status": "success",
                "response": response,
                "text": response.text,
                "tool_calls": self.extract_tool_calls(response)
            }
        except Exception as e:
            return {
                "status": "error",
                "message": str(e)
            }
    
    def extract_tool_calls(self, response):
        """Tool calls ko extract karo response se"""
        tool_calls = []
        
        # Gemini specific parsing
        if hasattr(response, 'parts'):
            for part in response.parts:
                if hasattr(part, 'function_call'):
                    tool_calls.append({
                        "name": part.function_call.name,
                        "args": dict(part.function_call.args)
                    })
        
        return tool_calls
    
    async def call_without_tools(self, prompt: str):
        """Simple text generation"""
        response = self.client.generate_content(prompt)
        return response.text
```

#### **2. Tool Schemas**
```python
# llm/tool_schemas.py
def get_tool_schemas():
    """
    LLM ke liye tools ka definition
    """
    return [
        {
            "name": "fetch_repository",
            "description": "GitHub repository se code fetch karna",
            "input_schema": {
                "type": "object",
                "properties": {
                    "github_url": {
                        "type": "string",
                        "description": "GitHub repository URL"
                    }
                },
                "required": ["github_url"]
            }
        },
        {
            "name": "analyze_code_structure",
            "description": "Code ka structure analyze karna (functions, classes, imports)",
            "input_schema": {
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "Analyze karne ke liye file path"
                    }
                },
                "required": ["file_path"]
            }
        },
        {
            "name": "security_audit",
            "description": "Code mein security vulnerabilities check karna",
            "input_schema": {
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "Audit karne ke liye file path"
                    }
                },
                "required": ["file_path"]
            }
        },
        {
            "name": "performance_analysis",
            "description": "Performance issues identify karna",
            "input_schema": {
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "Analyze karne ke liye file path"
                    }
                },
                "required": ["file_path"]
            }
        }
    ]
```

#### **3. System Prompts**
```python
# llm/prompts.py

SYSTEM_PROMPT = """
You are an expert AI code reviewer agent. Your goal is to provide thorough, 
professional code analysis and recommendations.

## Your Capabilities:
You have access to specialized tools for code analysis:
1. fetch_repository - Download code from GitHub
2. analyze_code_structure - Understand code organization
3. security_audit - Check for security vulnerabilities
4. performance_analysis - Identify performance issues

## Your Analysis Process:

STEP 1: Fetch the Code
- Use fetch_repository tool with the provided GitHub URL
- Understand the project structure and main files

STEP 2: Structural Analysis
- Use analyze_code_structure for each important file
- Identify functions, classes, and dependencies
- Check for code organization and modularity

STEP 3: Security Review
- Use security_audit tool on all files
- Look for hardcoded secrets, injection vulnerabilities
- Check for unsafe operations

STEP 4: Performance Check
- Use performance_analysis tool
- Identify bottlenecks and inefficiencies
- Look for O(n²) algorithms, memory leaks

STEP 5: Generate Report
- Compile findings into structured report
- Provide actionable recommendations
- Give code quality score

## Output Format:
Always provide:
1. Quality Score (0-100)
2. Critical Issues (must fix)
3. Major Issues (should fix)
4. Minor Issues (nice to fix)
5. Recommendations
6. Code Examples for fixes

Be thorough, professional, and constructive in your feedback.
"""

FEW_SHOT_EXAMPLES = """
Example 1: Security Issue
Code: password = "admin123"
Issue: Hardcoded credentials
Recommendation: Use environment variables with python-dotenv

Example 2: Performance Issue
Code: 
for i in range(n):
    for j in range(n):
        list.append(i + j)
Issue: O(n²) complexity
Recommendation: Use list comprehension or vectorization
"""
```

#### **4. Response Parser**
```python
# llm/response_parser.py
import json
import re

def parse_llm_response(response_text: str):
    """
    LLM response ko parse karo aur structured format mein convert karo
    """
    parsed = {
        "quality_score": 0,
        "critical_issues": [],
        "major_issues": [],
        "minor_issues": [],
        "recommendations": [],
        "summary": ""
    }
    
    # Quality score extract karo
    score_match = re.search(r"score.*?(\d+)/100", response_text, re.IGNORECASE)
    if score_match:
        parsed["quality_score"] = int(score_match.group(1))
    
    # Issues extract karo
    sections = response_text.split('\n\n')
    for section in sections:
        if "critical" in section.lower():
            parsed["critical_issues"] = extract_issues(section)
        elif "major" in section.lower():
            parsed["major_issues"] = extract_issues(section)
        elif "minor" in section.lower():
            parsed["minor_issues"] = extract_issues(section)
        elif "recommendation" in section.lower():
            parsed["recommendations"] = extract_recommendations(section)
    
    return parsed

def extract_issues(section: str):
    """Issues list extract karo"""
    issues = []
    lines = section.split('\n')
    for line in lines:
        if line.strip().startswith('-') or line.strip().startswith('•'):
            issues.append(line.strip())
    return issues
```

### **Deliverables**
- ✅ `llm/llm_client.py` - LLM API integration
- ✅ `llm/tool_schemas.py` - Tool definitions
- ✅ `llm/prompts.py` - System prompts
- ✅ `llm/response_parser.py` - Response parsing
- ✅ `LLM_INTEGRATION.md` - Documentation
- ✅ `test_llm.py` - Integration tests
- ✅ `.env.example` - API key template

### **Dependencies**
- Depends on: Person 2 (Tools for schemas)
- Required by: Person 1 (Agent), Person 4 (API)
- Libraries: `google-generativeai` OR `openai`

### **API Key Setup**
```bash
# Gemini (Free)
# Get from: https://makersuite.google.com/app/apikey

# OR OpenAI (Paid, $5 free credits)
# Get from: https://platform.openai.com/api-keys
```

### **Success Criteria**
- [ ] LLM properly call ho
- [ ] Tool calls extract ho
- [ ] Responses parse ho correctly
- [ ] Cost optimize ho (free tier fit ho)

---

## 👤 Person 4: "Backend Developer"

### **Primary Role**
FastAPI server build karna, API routes, database setup, production ready backend

### **Responsibilities**

| Component | Task |
|-----------|------|
| **FastAPI Server** | Routes, endpoints, middleware |
| **Database** | SQLite schema, CRUD operations |
| **API Documentation** | OpenAPI/Swagger docs |
| **Error Handling** | Graceful error responses |
| **Logging** | Request/response logging |

### **Code Responsibilities**

```python
Files to Create:
├── main.py                    ← FastAPI app entry
├── config.py                  ← Configuration
├── models.py                  ← Pydantic models
├── database.py                ← SQLite setup
├── api/
│   ├── __init__.py
│   ├── routes.py              ← API endpoints
│   └── dependencies.py        ← Dependency injection
├── schemas/
│   ├── review.py              ← Review schema
│   └── responses.py           ← Response schemas
├── utils/
│   ├── logger.py              ← Logging
│   └── exceptions.py          ← Custom exceptions
└── tests/
    └── test_api.py            ← API tests
```

### **Detailed Code Tasks**

#### **1. Main FastAPI App**
```python
# main.py
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging

# Database setup
from database import init_db, SessionLocal

# Logging setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Startup event
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Starting up...")
    init_db()
    yield
    # Shutdown
    logger.info("Shutting down...")

app = FastAPI(
    title="Code Review Agent API",
    description="AI-powered code review using Gemini",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware - Streamlit ke liye
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Production mein specific domains
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routes import
from api.routes import router

app.include_router(router, prefix="/api")

# Health check
@app.get("/health")
async def health_check():
    return {"status": "ok", "message": "Server is running"}

# Root
@app.get("/")
async def root():
    return {
        "name": "Code Review Agent API",
        "version": "1.0.0",
        "docs": "/docs"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
```

#### **2. Pydantic Models**
```python
# models.py
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime

class ReviewRequest(BaseModel):
    github_url: Optional[str] = Field(None, description="GitHub repository URL")
    code_content: Optional[str] = Field(None, description="Code to review directly")
    analysis_type: str = Field("full", description="Type: full, security, performance")
    
    class Config:
        example = {
            "github_url": "https://github.com/user/repo",
            "analysis_type": "full"
        }

class Issue(BaseModel):
    type: str
    severity: str  # CRITICAL, HIGH, MEDIUM, LOW
    message: str
    suggestion: Optional[str] = None
    line_number: Optional[int] = None

class ReviewResponse(BaseModel):
    status: str
    review_id: str
    quality_score: float
    total_issues: int
    critical_issues: int
    security_issues: int
    performance_issues: int
    issues: List[Issue]
    report: str
    timestamp: datetime

class ReviewHistory(BaseModel):
    review_id: str
    code_source: str  # github or direct
    quality_score: float
    total_issues: int
    timestamp: datetime
```

#### **3. Database Setup**
```python
# database.py
from sqlalchemy import create_engine, Column, String, Float, Integer, DateTime, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime

DATABASE_URL = "sqlite:///./reviews.db"

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False}
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Models
class ReviewRecord(Base):
    __tablename__ = "reviews"
    
    id = Column(String, primary_key=True, index=True)
    code_source = Column(String)  # github or direct
    github_url = Column(String, nullable=True)
    quality_score = Column(Float)
    total_issues = Column(Integer)
    critical_issues = Column(Integer)
    security_issues = Column(Integer)
    performance_issues = Column(Integer)
    report = Column(Text)
    timestamp = Column(DateTime, default=datetime.utcnow)
    
def init_db():
    """Create all tables"""
    Base.metadata.create_all(bind=engine)

def get_db():
    """Dependency for database session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

#### **4. API Routes**
```python
# api/routes.py
from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List
import uuid
from datetime import datetime

from models import ReviewRequest, ReviewResponse, ReviewHistory
from database import ReviewRecord, get_db
from agent.agent_core import CodeReviewAgent

router = APIRouter()

# Initialize agent (ideally in config)
from llm.llm_client import LLMClient
import os

llm_client = LLMClient(api_key=os.getenv("GEMINI_API_KEY"))
agent = CodeReviewAgent(llm_client)

@router.post("/review", response_model=ReviewResponse)
async def start_review(
    request: ReviewRequest,
    db: Session = Depends(get_db)
):
    """
    Code review start karo
    """
    try:
        # Input validation
        if not request.github_url and not request.code_content:
            raise HTTPException(
                status_code=400,
                detail="Either github_url or code_content required"
            )
        
        # Agent ko call karo
        review_result = await agent.review_code(
            github_url=request.github_url,
            code_content=request.code_content,
            analysis_type=request.analysis_type
        )
        
        # Database mein save karo
        review_id = str(uuid.uuid4())
        review_record = ReviewRecord(
            id=review_id,
            code_source="github" if request.github_url else "direct",
            github_url=request.github_url,
            quality_score=review_result["quality_score"],
            total_issues=len(review_result["issues"]),
            critical_issues=len([i for i in review_result["issues"] if i["severity"] == "CRITICAL"]),
            security_issues=len([i for i in review_result["issues"] if i["type"] == "Security"]),
            performance_issues=len([i for i in review_result["issues"] if i["type"] == "Performance"]),
            report=review_result["report"],
            timestamp=datetime.utcnow()
        )
        db.add(review_record)
        db.commit()
        
        return ReviewResponse(
            status="success",
            review_id=review_id,
            quality_score=review_result["quality_score"],
            total_issues=len(review_result["issues"]),
            critical_issues=review_record.critical_issues,
            security_issues=review_record.security_issues,
            performance_issues=review_record.performance_issues,
            issues=review_result["issues"],
            report=review_result["report"],
            timestamp=review_record.timestamp
        )
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/review/{review_id}")
async def get_review(review_id: str, db: Session = Depends(get_db)):
    """
    Previous review ko retrieve karo
    """
    review = db.query(ReviewRecord).filter(ReviewRecord.id == review_id).first()
    
    if not review:
        raise HTTPException(status_code=404, detail="Review not found")
    
    return {
        "review_id": review.id,
        "quality_score": review.quality_score,
        "issues": review.total_issues,
        "report": review.report,
        "timestamp": review.timestamp
    }

@router.get("/reviews/history")
async def get_review_history(db: Session = Depends(get_db)):
    """
    Sab reviews ka history
    """
    reviews = db.query(ReviewRecord).order_by(ReviewRecord.timestamp.desc()).limit(20).all()
    
    return [
        {
            "review_id": r.id,
            "code_source": r.code_source,
            "quality_score": r.quality_score,
            "issues": r.total_issues,
            "timestamp": r.timestamp
        }
        for r in reviews
    ]

@router.post("/review/async")
async def async_review(
    request: ReviewRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    Long-running reviews ke liye async endpoint
    """
    review_id = str(uuid.uuid4())
    
    # Background task mein add karo
    background_tasks.add_task(
        process_review,
        review_id,
        request,
        db
    )
    
    return {
        "status": "processing",
        "review_id": review_id,
        "message": "Review is being processed"
    }

async def process_review(review_id: str, request: ReviewRequest, db: Session):
    """Background mein review process karo"""
    try:
        result = await agent.review_code(
            github_url=request.github_url,
            code_content=request.code_content
        )
        # Save to DB
    except Exception as e:
        logger.error(f"Review processing failed: {str(e)}")
```

### **Deliverables**
- ✅ `main.py` - FastAPI server
- ✅ `config.py` - Configuration
- ✅ `models.py` - Pydantic models
- ✅ `database.py` - SQLite setup
- ✅ `api/routes.py` - API endpoints
- ✅ `requirements.txt` - Dependencies
- ✅ `API_DOCUMENTATION.md` - Endpoint docs
- ✅ `test_api.py` - Integration tests

### **Dependencies**
- Depends on: Person 1 (Agent), Person 3 (LLM)
- Required by: Person 5 (Frontend)
- Libraries: `FastAPI`, `SQLAlchemy`, `Pydantic`

### **Running the Server**
```bash
# Install dependencies
pip install -r requirements.txt

# Run server
python main.py

# Check docs
# Open: http://localhost:8000/docs
```

### **Success Criteria**
- [ ] Server localhost:8000 pe run ho
- [ ] All endpoints working ho
- [ ] Database save/retrieve ho
- [ ] CORS enabled ho

---

## 👤 Person 5: "Frontend + DevOps Developer"

### **Primary Role**
Beautiful Streamlit UI banayein, testing, deployment ready karna

### **Responsibilities**

| Area | Task |
|------|------|
| **Frontend UI** | Streamlit interface design |
| **UX/UX** | User experience, layouts |
| **Testing** | E2E testing, manual testing |
| **Deployment** | Streamlit Cloud, Docker |
| **Documentation** | User guide, setup guide |

### **Code Responsibilities**

```python
Files to Create:
├── streamlit_app.py           ← Main UI
├── components/
│   ├── __init__.py
│   ├── header.py              ← Header component
│   ├── input_section.py       ← Input component
│   ├── results_display.py     ← Results component
│   └── history.py             ← History component
├── config.py                  ← Streamlit config
├── utils/
│   ├── api_client.py          ← API calls
│   └── formatters.py          ← Data formatting
├── requirements.txt
├── .streamlit/
│   └── config.toml
└── tests/
    └── test_ui.py
```

### **Detailed Code Tasks**

#### **1. Main Streamlit App**
```python
# streamlit_app.py
import streamlit as st
import pandas as pd
import requests
from datetime import datetime
import json

# Page config
st.set_page_config(
    page_title="Code Review Agent",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
<style>
    .metric-card {
        padding: 20px;
        background-color: #f0f2f6;
        border-radius: 8px;
        margin: 10px 0;
    }
    .critical {color: #ff3333;}
    .high {color: #ff9933;}
    .medium {color: #ffcc00;}
    .low {color: #00cc00;}
</style>
""", unsafe_allow_html=True)

# Session state
if "api_endpoint" not in st.session_state:
    st.session_state.api_endpoint = "http://localhost:8000"
if "review_result" not in st.session_state:
    st.session_state.review_result = None
if "review_history" not in st.session_state:
    st.session_state.review_history = []

# Header
st.title("🔍 AI Code Reviewer Agent")
st.markdown("Professional code analysis powered by **Gemini AI**")

# Sidebar
with st.sidebar:
    st.header("⚙️ Configuration")
    
    api_endpoint = st.text_input(
        "API Endpoint",
        value=st.session_state.api_endpoint,
        help="FastAPI server address"
    )
    st.session_state.api_endpoint = api_endpoint
    
    analysis_type = st.selectbox(
        "Analysis Type",
        ["Full Review", "Security Only", "Performance Only"],
        help="What type of review?"
    )
    
    st.divider()
    st.markdown("### 📚 About")
    st.info("""
    This agent analyzes code for:
    - 🐛 Bugs and issues
    - 🔒 Security vulnerabilities
    - ⚡ Performance problems
    - 📋 Code quality metrics
    - 💡 Best practices
    """)

# Main content
col1, col2 = st.columns([2, 1])

with col1:
    st.subheader("📝 Code Input")
    
    # Input method
    input_method = st.radio(
        "How to input code?",
        ["GitHub URL", "Direct Code Paste"],
        horizontal=True
    )
    
    if input_method == "GitHub URL":
        code_input = st.text_input(
            "GitHub Repository URL",
            placeholder="https://github.com/username/repo",
            help="Public GitHub repository link"
        )
        input_type = "github"
    else:
        code_input = st.text_area(
            "Paste your code here",
            height=300,
            placeholder="def example():\n    pass",
            help="Paste Python, JavaScript, or any code"
        )
        input_type = "direct"

with col2:
    st.subheader("⚡ Quick Actions")
    
    col_submit, col_clear = st.columns(2)
    
    with col_submit:
        submit_button = st.button(
            "🚀 Start Review",
            use_container_width=True,
            type="primary"
        )
    
    with col_clear:
        clear_button = st.button(
            "🗑️ Clear",
            use_container_width=True
        )
    
    if clear_button:
        st.session_state.review_result = None
        code_input = ""
        st.rerun()

# Processing
if submit_button and code_input:
    with st.spinner("🤔 Agent is reviewing your code..."):
        try:
            # API call
            payload = {
                "analysis_type": analysis_type.lower().replace(" ", "_")
            }
            
            if input_type == "github":
                payload["github_url"] = code_input
            else:
                payload["code_content"] = code_input
            
            response = requests.post(
                f"{st.session_state.api_endpoint}/api/review",
                json=payload,
                timeout=120
            )
            
            if response.status_code == 200:
                result = response.json()
                st.session_state.review_result = result
                
                st.success("✅ Review Complete!")
                
            else:
                st.error(f"❌ Error: {response.json().get('detail', 'Unknown error')}")
        
        except requests.exceptions.ConnectionError:
            st.error("❌ Cannot connect to API. Make sure FastAPI server is running!")
        except Exception as e:
            st.error(f"❌ Error: {str(e)}")

# Display results
if st.session_state.review_result:
    result = st.session_state.review_result
    
    st.divider()
    st.subheader("📊 Review Results")
    
    # Metrics
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            "Quality Score",
            f"{result['quality_score']}/100",
            delta="Code Quality"
        )
    
    with col2:
        st.metric(
            "Total Issues",
            result['total_issues'],
            delta="Found"
        )
    
    with col3:
        st.metric(
            "🔒 Security",
            result['security_issues'],
            delta="Issues"
        )
    
    with col4:
        st.metric(
            "⚡ Performance",
            result['performance_issues'],
            delta="Issues"
        )
    
    # Severity breakdown
    st.subheader("🔍 Issues Breakdown")
    
    if result['issues']:
        # Create DataFrame
        issues_data = []
        for issue in result['issues']:
            issues_data.append({
                "Type": issue['type'],
                "Severity": issue['severity'],
                "Message": issue['message'],
                "Suggestion": issue.get('suggestion', 'N/A')
            })
        
        df = pd.DataFrame(issues_data)
        
        # Color code by severity
        def color_severity(val):
            if val == "CRITICAL":
                return "color: white; background-color: #ff3333"
            elif val == "HIGH":
                return "color: white; background-color: #ff9933"
            elif val == "MEDIUM":
                return "color: black; background-color: #ffcc00"
            else:
                return "color: white; background-color: #00cc00"
        
        st.dataframe(
            df.style.applymap(color_severity, subset=["Severity"]),
            use_container_width=True
        )
    else:
        st.success("🎉 No issues found! Great code!")
    
    # Full report
    st.subheader("📋 Detailed Report")
    
    with st.expander("Read Full Report", expanded=True):
        st.markdown(result['report'])
    
    # Download
    col1, col2 = st.columns(2)
    
    with col1:
        st.download_button(
            label="📥 Download as Markdown",
            data=result['report'],
            file_name=f"code_review_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md",
            mime="text/markdown"
        )
    
    with col2:
        # JSON download
        json_data = json.dumps(result, indent=2, default=str)
        st.download_button(
            label="💾 Download as JSON",
            data=json_data,
            file_name=f"code_review_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
            mime="application/json"
        )

# History section
st.divider()
st.subheader("📜 Review History")

try:
    history = requests.get(
        f"{st.session_state.api_endpoint}/api/reviews/history"
    ).json()
    
    if history:
        history_df = pd.DataFrame(history)
        st.dataframe(history_df, use_container_width=True)
    else:
        st.info("No reviews yet. Start by reviewing code above!")

except:
    st.warning("Cannot fetch history. Make sure API is running.")
```

#### **2. Streamlit Config**
```toml
# .streamlit/config.toml
[theme]
primaryColor = "#3b5bdb"
backgroundColor = "#ffffff"
secondaryBackgroundColor = "#f0f2f6"
textColor = "#262730"
font = "sans serif"

[client]
showErrorDetails = true
toolbarMode = "minimal"

[server]
maxUploadSize = 200
enableCORS = true
```

#### **3. API Client Utility**
```python
# utils/api_client.py
import requests
from typing import Optional
import logging

logger = logging.getLogger(__name__)

class APIClient:
    def __init__(self, endpoint: str):
        self.endpoint = endpoint
    
    async def review_code(self, github_url: Optional[str] = None, code_content: Optional[str] = None):
        """Code review karo"""
        try:
            payload = {}
            if github_url:
                payload["github_url"] = github_url
            if code_content:
                payload["code_content"] = code_content
            
            response = requests.post(
                f"{self.endpoint}/api/review",
                json=payload,
                timeout=120
            )
            
            return response.json()
        except Exception as e:
            logger.error(f"API Error: {str(e)}")
            raise
    
    def get_history(self):
        """Review history fetch karo"""
        try:
            response = requests.get(
                f"{self.endpoint}/api/reviews/history"
            )
            return response.json()
        except Exception as e:
            logger.error(f"API Error: {str(e)}")
            return []
```

### **Deliverables**
- ✅ `streamlit_app.py` - Main UI
- ✅ `components/` - UI components
- ✅ `utils/api_client.py` - API integration
- ✅ `requirements.txt` - Dependencies
- ✅ `.streamlit/config.toml` - Streamlit config
- ✅ `test_ui.py` - UI tests
- ✅ `USER_GUIDE.md` - How to use
- ✅ `DEPLOYMENT.md` - Deployment guide
- ✅ `Dockerfile` - Docker setup (optional)

### **Dependencies**
- Depends on: Person 4 (Backend API)
- Required by: None
- Libraries: `Streamlit`, `requests`, `pandas`

### **Running Locally**
```bash
# Install
pip install -r requirements.txt

# Run
streamlit run streamlit_app.py

# Access
# Open: http://localhost:8501
```

### **Deployment Options**

**Option 1: Streamlit Cloud (FREE)**
```bash
git push origin main
# Go to https://streamlit.io/cloud
# Deploy from GitHub repo
```

**Option 2: Docker**
```bash
docker build -t code-review-agent .
docker run -p 8501:8501 code-review-agent
```

### **Success Criteria**
- [ ] UI beautiful aur responsive ho
- [ ] API calls working ho
- [ ] History display ho
- [ ] Downloads working ho

---

## 📅 Development Timeline (2 Weeks)

```
WEEK 1:
├── Day 1-2: Setup + Planning
│   ├── All members: GitHub repo setup
│   ├── All members: Environment setup
│   └── Team lead: Architecture review
│
├── Day 3: Core Development Starts
│   ├── Person 1: Agent skeleton
│   ├── Person 2: Tool templates
│   ├── Person 3: LLM client setup
│   ├── Person 4: Database schema
│   └── Person 5: UI mockups
│
├── Day 4: Implementation
│   ├── Person 1: ReACT loop
│   ├── Person 2: Tools (github, analyzer)
│   ├── Person 3: Prompt engineering
│   ├── Person 4: FastAPI routes
│   └── Person 5: Streamlit components
│
└── Day 5: Integration Sprint
    ├── All: Integration testing
    ├── Person 1 + 2: Agent-Tool testing
    ├── Person 3 + 4: LLM-API testing
    └── Person 5: UI-API testing

WEEK 2:
├── Day 1: Bug Fixing
│   ├── All: Debug + fix issues
│   └── Daily standups
│
├── Day 2-3: Feature Completion
│   ├── Person 2: Security + Performance tools
│   ├── Person 3: Response parsing
│   ├── Person 4: Database queries
│   └── Person 5: History + downloads
│
├── Day 4: Testing + Documentation
│   ├── Person 5: E2E testing
│   ├── All: Write documentation
│   └── All: Create user guide
│
└── Day 5: Final Polish + Deployment
    ├── All: Final testing
    ├── Person 4: Render deployment
    ├── Person 5: Streamlit Cloud deployment
    └── All: Demo + presentation ready
```

---

## 🔄 Inter-Team Communication

### **Daily Standups (10 AM)**
```
- Person 1: What's done? What's blocking?
- Person 2: Tools ready? Any issues?
- Person 3: Prompts working? Costs?
- Person 4: API ready? DB working?
- Person 5: UI done? API integration okay?
```

### **Integration Points**
```
Person 1 ←→ Person 2: Agent calls tools
Person 1 ←→ Person 3: LLM for decision making
Person 1 ←→ Person 4: Result saving
Person 2 ← → Person 3: Tool schemas
Person 3 ←→ Person 4: API response format
Person 4 ←→ Person 5: API endpoints
```

---

## 📋 Submission Checklist

### **Code Quality**
- [ ] All code commented (Urdu/English)
- [ ] Following Python PEP8
- [ ] No hardcoded secrets
- [ ] Error handling everywhere
- [ ] Type hints used

### **Documentation**
- [ ] README.md complete
- [ ] Setup instructions clear
- [ ] API documentation done
- [ ] Architecture diagram
- [ ] User guide written

### **Testing**
- [ ] Unit tests for each component
- [ ] Integration tests working
- [ ] Manual testing done
- [ ] Edge cases handled

### **Deployment**
- [ ] Backend deployed (Render)
- [ ] Frontend deployed (Streamlit Cloud)
- [ ] Live demo working
- [ ] Environment variables configured

### **Presentation**
- [ ] Demo video prepared
- [ ] Slide deck ready
- [ ] Live demo planned
- [ ] Q&A prep done

---

## 🎓 Learning Outcomes

**After this project, team will have learned:**

1. **Agentic AI Fundamentals**
   - ReACT framework
   - Tool use patterns
   - Agent loops

2. **Full Stack Development**
   - Backend (FastAPI)
   - Frontend (Streamlit)
   - Database (SQLite)

3. **LLM Integration**
   - API calling
   - Prompt engineering
   - Response parsing

4. **Collaboration**
   - Git workflows
   - Code review
   - Team coordination

5. **Deployment**
   - Production setup
   - Environment management
   - Cloud deployment

---

## 🚀 Resources & References

**Learning Resources:**
- [Anthropic Prompt Engineering](https://docs.anthropic.com)
- [FastAPI Tutorial](https://fastapi.tiangolo.com)
- [Streamlit Docs](https://docs.streamlit.io)
- [Gemini API Guide](https://ai.google.dev/gemini-api)
- [ReACT Paper](https://arxiv.org/abs/2210.03629)

**Tools:**
- GitHub: Code management
- VS Code: Development
- Postman: API testing
- Git Bash: Version control

---

## 📞 Support & Questions

**If stuck:**
1. Check documentation
2. Ask in team chat
3. Pair program with another member
4. Consult Person 1 (lead)

---

**Last Updated:** January 2025  
**Status:** Ready for Implementation  
**Difficulty:** Intermediate to Advanced
