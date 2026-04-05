"""
Tool/function calling type definitions.
"""

from dataclasses import dataclass
from typing import Optional, Dict, Any


@dataclass
class ToolParameter:
    """Definition of a tool parameter."""
    name: str
    type: str
    description: str
    required: bool = True


@dataclass
class ToolSchema:
    """Schema definition for a tool."""
    name: str
    description: str
    parameters: list[ToolParameter]
    required: list[str] | None = None


@dataclass
class ToolCall:
    """A tool call from the AI model."""
    tool_name: str
    parameters: Dict[str, Any]
    tool_call_id: str | None = None


@dataclass
class ToolResult:
    """Result of a tool execution."""
    tool_name: str
    tool_call_id: str | None
    content: str
    success: bool = True
    error: str | None = None
