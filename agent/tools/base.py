"""
Tool Base Interface - sab tools ke liye standard contract.
Person 2 is BaseTool ko inherit karke apne custom tools banayega.
"""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ToolResult:
    """
    Tool execution ka standardized result.
    Tool khud decide karta hai ke success hai ya nahi.
    """
    success: bool
    data: Any
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_observation(self) -> str:
        """
        Observation ko text mein convert karo - LLM ko feed karne ke liye.
        Complex data ko JSON-serialize karte hain.
        """
        if not self.success:
            return f"ERROR: {self.error or 'Tool failed'}"
        if isinstance(self.data, str):
            return self.data
        try:
            return json.dumps(self.data, ensure_ascii=False, indent=2)
        except (TypeError, ValueError):
            return str(self.data)


@dataclass
class ToolSchema:
    """
    Tool ka JSON-Schema style description.
    LLM ko batata hai ke tool kya karta hai aur input ka shape kya hai.
    """
    name: str
    description: str
    parameters: dict[str, Any]
    required: list[str] = field(default_factory=list)

    def to_openai_tool(self) -> dict[str, Any]:
        """OpenAI function calling format mein convert karo."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": self.parameters,
                    "required": self.required,
                },
            },
        }


class BaseTool(ABC):
    """
    Abstract base class for all tools.
    Har tool ko yeh implement karna hoga:
    1. schema() - apna description return karo
    2. run() - actual logic execute karo

    Optional: validate_input() - input sanitization ke liye
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Tool ka unique naam - registry mein is se identify hota hai."""
        ...

    @property
    @abstractmethod
    def description(self) -> str:
        """LLM ke liye tool ka description - kab use karna hai yeh yahan likho."""
        ...

    @abstractmethod
    async def run(self, tool_input: dict[str, Any]) -> ToolResult:
        """
        Tool ka main logic.
        ToolInput dict mein aata hai, ToolResult return karna hota hai.
        Errors ko catch karke ToolResult(success=False) return karo.
        """
        ...

    def validate_input(self, tool_input: dict[str, Any]) -> tuple[bool, str | None]:
        """
        Input validate karo - required fields check karta hai.
        Override karke custom validation add kar sakte ho.
        Returns: (is_valid, error_message)
        """
        schema = self.schema()
        for req in schema.required:
            if req not in tool_input:
                return False, f"Missing required field: {req}"
        return True, None

    def schema(self) -> ToolSchema:
        """Default schema - subclasses apna override kar sakti hain."""
        return ToolSchema(
            name=self.name,
            description=self.description,
            parameters={},
            required=[],
        )
