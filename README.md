# Code Review Agent

AI-powered code review agent built with a **ReACT (Reason + Act) loop architecture**.
Multi-person team project - FastAPI backend + Streamlit frontend + LLM-powered reasoning.

## Team Structure (5 Members)

| Person | Role | Owns |
|--------|------|------|
| **Person 1 (You)** | Agent Architect | ReACT loop, state, memory, tool orchestration |
| **Person 2** | Tool Engineer | Linter, security scanner, code analyzer tools |
| **Person 3** | LLM Engineer | Gemini/OpenAI provider implementations |
| **Person 4** | Backend Engineer | FastAPI endpoints, request/response models |
| **Person 5** | Frontend Engineer | Streamlit UI, chat interface |

## Architecture (Person 1's Domain)

```
agent/
  core/
    react_loop.py       # Think -> Act -> Observe -> Reflect
    state.py            # Agent state + multi-session StateManager
    orchestrator.py     # Single/parallel/sequential tool execution
  memory/
    conversation.py     # Multi-session chat history
    context.py          # Token budget + context window trimming
  tools/
    base.py             # BaseTool ABC + ToolResult + ToolSchema
    registry.py         # Tool registration & discovery
  llm/
    client.py           # LLMClient ABC (Person 3 implements providers)
  prompts/
    system.py           # Centralized system prompts
  agent.py              # CodeReviewAgent - main integration class
```

## Key Design Decisions

- **Provider-agnostic LLM**: Agent sirf `LLMClient` interface se baat karta hai.
  Person 3 Gemini/OpenAI implementations add karega bina core code touch kiye.
- **Tool contract via `BaseTool`**: Person 2 ke tools ek standard interface follow karte hain.
  Registry-based discovery - dynamic tool loading.
- **Multi-session support**: `session_id` ke through parallel users handle hote hain.
  State aur memory dono per-session isolated hain.
- **Bounded resources**: Max iterations, timeouts, message limits production safety ke liye.

## Quick Start

```bash
# 1. Clone and setup
cd Code-Review-Agent
python -m venv venv
venv\Scripts\activate          # Windows
# source venv/bin/activate     # Linux/Mac

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure environment
copy .env.example .env         # Windows
# cp .env.example .env         # Linux/Mac
# Edit .env and add your API keys

# 4. Run tests
pytest

# 5. (Person 4) Start API
uvicorn api.main:app --reload

# 6. (Person 5) Start frontend
streamlit run frontend/app.py
```

## Basic Usage Example

```python
import asyncio
from agent.agent import CodeReviewAgent
from agent.llm.client import MockLLMClient
from agent.tools.base import BaseTool, ToolResult

# Custom tool (Person 2 banayega)
class CodeLengthTool(BaseTool):
    @property
    def name(self) -> str:
        return "code_length"
    @property
    def description(self) -> str:
        return "Counts lines in a code snippet"
    async def run(self, tool_input):
        code = tool_input.get("code", "")
        return ToolResult(success=True, data={"lines": len(code.splitlines())})

async def main():
    # Agent setup
    agent = CodeReviewAgent(llm=MockLLMClient())
    agent.register_tool(CodeLengthTool())

    # Review request
    result = await agent.review(
        code_or_question="def hello():\n    print('hi')",
        session_id="user_1",
    )
    print(result.final_answer)
    print(f"Status: {result.status}, Iterations: {result.iterations_used}")

asyncio.run(main())
```

## Integration Points (For Other Team Members)

### Person 2 (Tools) - Add custom tool:
```python
from agent.tools.base import BaseTool, ToolResult

class MyTool(BaseTool):
    @property
    def name(self) -> str: return "my_tool"

    @property
    def description(self) -> str: return "What this tool does"

    async def run(self, tool_input: dict) -> ToolResult:
        return ToolResult(success=True, data={"result": "..."})

# Register it
agent.register_tool(MyTool())
```

### Person 3 (LLM) - Add Gemini provider:
```python
from agent.llm.client import LLMClient, LLMResponse, LLMProvider

class GeminiClient(LLMClient):
    provider = LLMProvider.GEMINI
    async def generate(self, prompt, system=None, **kwargs) -> LLMResponse:
        # Your Gemini API call here
        return LLMResponse(content="...", provider=LLMProvider.GEMINI, model="gemini-2.0-flash")
    # Implement chat() and generate_with_tools() too
```

### Person 4 (API) - Expose agent:
```python
from fastapi import FastAPI
from agent.agent import CodeReviewAgent

app = FastAPI()
agent = CodeReviewAgent(llm=...)  # Person 3 provides LLM

@app.post("/review")
async def review(code: str, session_id: str = "default"):
    result = await agent.review(code, session_id=session_id)
    return {"answer": result.final_answer, "status": result.status}
```

## Configuration

All settings via environment variables (see `.env.example`):

| Variable | Default | Description |
|----------|---------|-------------|
| `LLM_PROVIDER` | `mock` | `gemini`, `openai`, or `mock` |
| `MAX_REACT_ITERATIONS` | `8` | Max ReACT loop iterations per task |
| `AGENT_TIMEOUT_SECONDS` | `120` | Total time limit per task |
| `MAX_CONTEXT_TOKENS` | `32000` | Context window size |

## Testing

```bash
pytest                          # Run all tests
pytest --cov=agent              # With coverage
pytest tests/test_agent.py      # Specific file
```

## License

MIT
