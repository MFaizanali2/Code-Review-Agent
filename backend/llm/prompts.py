SYSTEM_PROMPT = """You are an expert AI Code Reviewer Agent. Your job is to analyze code professionally.

## 🎯 Your Role
You are a senior developer jo code reviews karta hai. Tumhe har file ko carefully analyze karna hai aur detailed feedback dena hai.

## 🔧 Tools Available
You have these tools:
1. **fetch_repository** — GitHub se code download karo
2. **analyze_code_structure** — Code ka structure samjho (functions, classes)
3. **security_audit** — Security vulnerabilities check karo
4. **performance_analysis** — Performance issues find karo
5. **read_file_content** — Kisi bhi file ka content padho
6. **generate_report** — Final report banao

## 📋 Analysis Process (FOLLOW THIS ORDER)

### STEP 1: Fetch & Understand
- Pehle repository fetch karo
- File structure dekho aur main files identify karo
- Project ka purpose samjho

### STEP 2: Deep Analysis
- Har important file ko read karo
- Code structure analyze karo
- Functions, classes, imports note karo

### STEP 3: Security Review
- Security vulnerabilities check karo
- CRITICAL issues pe focus karo
- Hardcoded secrets, injections, unsafe code

### STEP 4: Performance Check
- Slow code patterns find karo
- Nested loops, memory issues, O(n²) complexity
- Optimization suggestions do

### STEP 5: Report Generation
- Saare findings ko compile karo
- Quality score do (0-100)
- Actionable recommendations do

## 📊 Scoring Guidelines
- **90-100**: Excellent — Production ready
- **70-89**: Good — Minor improvements needed
- **50-69**: Average — Major issues found
- **30-49**: Poor — Significant rework needed
- **0-29**: Critical — Complete rewrite recommended

## ⚠️ Critical Checks (ALWAYS DO THESE)
1. Hardcoded secrets (passwords, API keys, tokens)
2. SQL injection vulnerabilities
3. Unsafe eval()/exec() usage
4. Path traversal vulnerabilities
5. Command injection risks
6. Insecure deserialization

## ✅ Best Practices (RECOMMEND THESE)
1. Follow project conventions
2. Use environment variables for secrets
3. Optimize loops and data structures
4. Add proper error handling
5. Use type hints
6. Remove dead code and debug statements

## 📤 Output Format
Always structure your final report like this:

```
## 📊 Quality Score: XX/100

## 🚨 Critical Issues (X)
- [description with line numbers]

## ⚠️ Major Issues (X)
- [description with line numbers]

## 📝 Minor Issues (X)
- [description with line numbers]

## 💡 Recommendations
- [actionable suggestions]

## 🔧 Code Examples
- [before/after code snippets]
```

## 🚫 Rules
1. NEVER make up issues — only report real problems
2. NEVER suggest removing functionality
3. ALWAYS give constructive feedback
4. ALWAYS explain WHY something is an issue
5. Use line numbers where possible
6. Be specific, not vague
"""

FEW_SHOT_EXAMPLES = [
    {
        "category": "Security",
        "code": """password = "admin123"
api_key = "sk-1234567890abcdef"
db.execute(f"SELECT * FROM users WHERE id = {user_input}")""",
        "analysis": {
            "issues": [
                {"type": "Hardcoded Secrets", "severity": "CRITICAL", "line": 1, "message": "Password hardcoded in source code", "fix": "Use environment variables: os.getenv('DB_PASSWORD')"},
                {"type": "Hardcoded Secrets", "severity": "CRITICAL", "line": 2, "message": "API key exposed in code", "fix": "Store in .env file and load with python-dotenv"},
                {"type": "SQL Injection", "severity": "CRITICAL", "line": 3, "message": "SQL injection vulnerability - f-string in query", "fix": "Use parameterized queries: db.execute('SELECT * FROM users WHERE id = ?', (user_input,))"},
            ],
            "score_impact": -30,
        },
    },
    {
        "category": "Performance",
        "code": """result = []
for i in range(len(data)):
    for j in range(len(data)):
        result.append(data[i] + data[j])

full_string = ""
for item in items:
    full_string += item + ","

big_list = list(range(1000000))""",
        "analysis": {
            "issues": [
                {"type": "Nested Loops", "severity": "HIGH", "line": 2, "message": "O(n²) complexity - nested loops", "fix": "Use itertools.product() or numpy broadcasting"},
                {"type": "String Concatenation", "severity": "MEDIUM", "line": 7, "message": "String concatenation in loop creates new string each iteration", "fix": "Use ','.join(items) - O(n) instead of O(n²)"},
                {"type": "Memory Usage", "severity": "LOW", "line": 10, "message": "Large list created in memory", "fix": "Use range() directly or generator: (x for x in range(1000000))"},
            ],
            "score_impact": -15,
        },
    },
    {
        "category": "Code Quality",
        "code": """def calc(a,b,c,d,e):
    x = a+b
    y = x*c
    z = y-d
    return z+e

def process():
    pass
    pass
    pass
    return None""",
        "analysis": {
            "issues": [
                {"type": "Unclear Function", "severity": "MEDIUM", "line": 1, "message": "Function name 'calc' is vague, too many parameters", "fix": "Rename to 'calculate_discount' with specific params"},
                {"type": "Dead Code", "severity": "LOW", "line": 7, "message": "Unnecessary pass statements", "fix": "Remove unused pass statements"},
                {"type": "Missing Type Hints", "severity": "LOW", "line": 1, "message": "No type hints on function parameters", "fix": "def calc(a: int, b: int, c: int, d: int, e: int) -> int:"},
            ],
            "score_impact": -10,
        },
    },
    {
        "category": "Error Handling",
        "code": """data = open("file.txt").read()
result = 100 / user_input
import requests
response = requests.get(url)""",
        "analysis": {
            "issues": [
                {"type": "Missing Error Handling", "severity": "HIGH", "line": 1, "message": "File not closed - resource leak, no exception handling", "fix": "Use 'with open(\"file.txt\") as f: data = f.read()'"},
                {"type": "Division by Zero", "severity": "CRITICAL", "line": 2, "message": "Potential ZeroDivisionError", "fix": "Check: if user_input != 0: result = 100 / user_input"},
                {"type": "Network Error", "severity": "MEDIUM", "line": 4, "message": "No try/except around network call", "fix": "Wrap in try/except for ConnectionError, Timeout"},
            ],
            "score_impact": -20,
        },
    },
    {
        "category": "Best Practices",
        "code": """import *
from module import *

MY_CONSTANT = 42
my_mixed_case = "bad"
MY_OTHER_CONSTANT = 56

def DoSomething():
    global MY_CONSTANT
    MY_CONSTANT = 100""",
        "analysis": {
            "issues": [
                {"type": "Wildcard Import", "severity": "MEDIUM", "line": 1, "message": "Wildcard import causes namespace pollution", "fix": "Import specific names: from module import specific_function"},
                {"type": "Naming Convention", "severity": "LOW", "line": 5, "message": "Variable uses mixed_case instead of snake_case", "fix": "Rename to: my_mixed_case_var"},
                {"type": "Global Variable", "severity": "MEDIUM", "line": 10, "message": "Modifying global variable in function", "fix": "Pass as parameter and return new value"},
            ],
            "score_impact": -8,
        },
    },
]


def get_review_prompt(repo_url: str = None, files_to_review: list[str] = None, focus_areas: list[str] = None) -> str:
    prompt_parts = ["## 📋 Code Review Request\n"]
    if repo_url:
        prompt_parts.append(f"**Repository:** {repo_url}\n")
    if files_to_review:
        prompt_parts.append(f"**Files to Review:** {', '.join(files_to_review)}\n")
    if focus_areas:
        prompt_parts.append(f"**Focus Areas:** {', '.join(focus_areas)}\n")
    prompt_parts.append("""
Please analyze the code and provide:
1. Quality score (0-100)
2. Critical issues (must fix)
3. Major issues (should fix)
4. Minor issues (nice to fix)
5. Specific recommendations
6. Code examples for fixes

Be thorough and constructive. Include line numbers.
    """)
    return "\n".join(prompt_parts)


def get_fix_prompt(error_message: str, code_snippet: str) -> str:
    return f"""## 🔧 Code Fix Request

**Error:**
```
{error_message}
```

**Code:**
```
{code_snippet}
```

Please:
1. Identify the root cause
2. Provide the fix
3. Explain why this fix works
4. Show before/after code
"""


def get_summary_prompt(findings: list[dict]) -> str:
    import json
    return f"""## 📊 Review Summary

**Findings:** {json.dumps(findings, indent=2, default=str)}

Please provide:
1. Overall quality score (0-100)
2. Top 3 most critical issues
3. Summary paragraph
4. 3 quick wins (easy fixes)
"""
