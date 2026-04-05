"""
Anthropic Claude provider implementation.
"""

import anthropic
from typing import List, Optional
from ai_companion.types.message import Message
from ai_companion.types.tool import ToolSchema, ToolCall
from .base import BaseProvider, LLMResponse
from ai_companion.config.schema import AppConfig


def _convert_tool_schema(schema: ToolSchema) -> dict:
    """Convert our tool schema to Anthropic format."""
    properties = {}
    required = []
    for param in schema.parameters:
        properties[param.name] = {
            "type": param.type,
            "description": param.description
        }
        if param.required:
            required.append(param.name)

    return {
        "name": schema.name,
        "description": schema.description,
        "input_schema": {
            "type": "object",
            "properties": properties,
            "required": required
        }
    }


def _extract_tool_calls(content: List[dict]) -> List[ToolCall]:
    """Extract tool calls from Anthropic response content."""
    tool_calls = []
    for block in content:
        if block["type"] == "tool_use":
            tool_calls.append(ToolCall(
                tool_name=block["name"],
                parameters=block["input"],
                tool_call_id=block.get("id")
            ))
    return tool_calls


class AnthropicProvider(BaseProvider):
    """Anthropic Claude LLM provider."""

    def __init__(self, config: AppConfig):
        self.config = config
        client_kwargs = {
            "api_key": config.anthropic_api_key
        }
        if config.anthropic_base_url:
            client_kwargs["base_url"] = config.anthropic_base_url
        self.client = anthropic.Anthropic(**client_kwargs)

    @property
    def provider_id(self) -> str:
        return "anthropic"

    def complete(
        self,
        messages: List[Message],
        system_prompt: str | None = None,
        tools: List[ToolSchema] | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
        model: str | None = None
    ) -> LLMResponse:
        # Convert messages to Anthropic format
        anthropic_messages = []
        for msg in messages:
            if isinstance(msg.content, str):
                anthropic_messages.append({
                    "role": msg.role,
                    "content": msg.content
                })
            else:
                anthropic_messages.append({
                    "role": msg.role,
                    "content": msg.content
                })

        # Build parameters
        params = {
            "model": model or self.config.default_model,
            "max_tokens": max_tokens or self.config.max_tokens,
            "messages": anthropic_messages,
        }

        if system_prompt is not None:
            params["system"] = system_prompt

        if temperature is not None:
            params["temperature"] = temperature

        if tools is not None and len(tools) > 0:
            params["tools"] = [_convert_tool_schema(t) for t in tools]

        response = self.client.messages.create(**params)

        # Extract content
        content: str | List[dict]
        if len(response.content) == 1 and response.content[0].type == "text":
            content = response.content[0].text
        else:
            content = [c.model_dump() for c in response.content]

        # Extract tool calls
        tool_calls = []
        if response.stop_reason == "tool_use":
            # Extract from actual response:
            tool_calls = []
            for block in response.content:
                if block.type == "tool_use":
                    tool_calls.append(ToolCall(
                        tool_name=block.name,
                        parameters=block.input,
                        tool_call_id=block.id
                    ))

        return LLMResponse(
            content=content,
            stop_reason=response.stop_reason,
            tool_calls=tool_calls,
            usage={
                "input_tokens": response.usage.input_tokens,
                "output_tokens": response.usage.output_tokens
            }
        )
