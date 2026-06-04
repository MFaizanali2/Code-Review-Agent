import asyncio
import json
from agent.agent import CodeReviewAgent
from agent.llm.client import MockLLMClient
from agent.tools.base import BaseTool, ToolResult


class DemoTool(BaseTool):
    @property
    def name(self):
        return "demo"

    @property
    def description(self):
        return "Demo tool that echoes input"

    async def run(self, tool_input):
        return ToolResult(success=True, data={"echo": tool_input})


async def main():
    mock_response = json.dumps({"type": "final_answer", "answer": "Code looks clean!"})
    agent = CodeReviewAgent(llm=MockLLMClient(default_response=mock_response))
    agent.register_tool(DemoTool())

    print("Agent stats:", agent.get_stats())

    result = await agent.review("Please review my code", session_id="demo_1")
    print("Status:", result.status)
    print("Answer:", result.final_answer)
    print("Iterations:", result.iterations_used)
    print("Duration:", f"{result.duration_seconds:.3f}s")
    print("Tool calls:", len(result.tool_calls))


asyncio.run(main())
