"""
Base provider interface.
Abstract base for different LLM providers (Anthropic, OpenAI, etc.)
"""

from abc import ABC, abstractmethod
from typing import List, Optional, Tuple
from ai_companion.types.message import Message
from ai_companion.types.tool import ToolSchema, ToolCall


class LLMResponse:
    """Response from an LLM provider."""
    def __init__(
        self,
        content: str | List[dict],
        stop_reason: str,
        tool_calls: List[ToolCall] | None = None,
        usage: dict | None = None
    ):
        self.content = content
        self.stop_reason = stop_reason
        self.tool_calls = tool_calls or []
        self.usage = usage or {}


class BaseProvider(ABC):
    """Abstract base class for LLM providers."""

    @property
    @abstractmethod
    def provider_id(self) -> str:
        """Unique identifier for this provider."""
        pass

    @abstractmethod
    def complete(
        self,
        messages: List[Message],
        system_prompt: str | None = None,
        tools: List[ToolSchema] | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
        model: str | None = None
    ) -> LLMResponse:
        """
        Generate a completion from the LLM.

        Args:
            messages: Conversation history
            system_prompt: Optional system prompt (some providers put this in messages)
            tools: Optional list of tool schemas
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature
            model: Model override

        Returns:
            LLMResponse with content, stop reason, and any tool calls
        """
        pass
