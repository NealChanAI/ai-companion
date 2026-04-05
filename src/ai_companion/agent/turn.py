"""
Conversation turn handling.
"""

from dataclasses import dataclass
from typing import Optional, List
from ai_companion.types.message import Message
from ai_companion.types.tool import ToolCall, ToolResult


@dataclass
class TurnResult:
    """Result from a single agent turn."""
    messages_added: List[Message]
    assistant_response: Optional[str]
    stop_reason: str
    tool_calls: List[ToolCall]
    complete: bool
    """Whether the turn is complete and we can respond to the user."""
