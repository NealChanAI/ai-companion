"""
OpenAI provider implementation.
"""

from openai import OpenAI
from typing import List, Optional
from ai_companion.types.message import Message
from ai_companion.types.tool import ToolSchema, ToolCall
from .base import BaseProvider, LLMResponse
from ai_companion.config.schema import AppConfig


def _convert_tool_schema(schema: ToolSchema) -> dict:
    """Convert our tool schema to OpenAI format."""
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
        "type": "function",
        "function": {
            "name": schema.name,
            "description": schema.description,
            "parameters": {
                "type": "object",
                "properties": properties,
                "required": required
            }
        }
    }


def _convert_messages(messages: List[Message], system_prompt: str | None) -> List[dict]:
    """Convert our message format to OpenAI format."""
    openai_messages = []
    if system_prompt is not None:
        openai_messages.append({
            "role": "system",
            "content": system_prompt
        })
    for msg in messages:
        if isinstance(msg.content, str):
            openai_messages.append({
                "role": msg.role,
                "content": msg.content
            })
        else:
            # Handle tool content blocks
            openai_messages.append({
                "role": msg.role,
                "content": msg.content
            })
    return openai_messages


def _extract_tool_calls(response) -> List[ToolCall]:
    """Extract tool calls from OpenAI response."""
    tool_calls = []
    if response.choices[0].message.tool_calls:
        for tc in response.choices[0].message.tool_calls:
            import json
            try:
                args = json.loads(tc.function.arguments)
            except json.JSONDecodeError:
                args = {}
            tool_calls.append(ToolCall(
                tool_name=tc.function.name,
                parameters=args,
                tool_call_id=tc.id
            ))
    return tool_calls


def _map_stop_reason(openai_stop_reason: str | None) -> str:
    """Map OpenAI stop reason to our stop reason format."""
    match openai_stop_reason:
        case "stop":
            return "end_turn"
        case "tool_calls":
            return "tool_use"
        case "length":
            return "max_tokens"
        case _:
            return openai_stop_reason or "end_turn"


class OpenAIProvider(BaseProvider):
    """OpenAI LLM provider."""

    def __init__(self, config: AppConfig):
        self.config = config
        client_kwargs = {
            "api_key": config.openai_api_key
        }
        if config.openai_base_url:
            client_kwargs["base_url"] = config.openai_base_url
        self.client = OpenAI(**client_kwargs)

    @property
    def provider_id(self) -> str:
        return "openai"

    def complete(
        self,
        messages: List[Message],
        system_prompt: str | None = None,
        tools: List[ToolSchema] | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
        model: str | None = None
    ) -> LLMResponse:
        openai_messages = _convert_messages(messages, system_prompt)

        params = {
            "model": model or self.config.default_model,
            "max_tokens": max_tokens or self.config.max_tokens,
            "messages": openai_messages,
        }

        if temperature is not None:
            params["temperature"] = temperature

        if tools is not None and len(tools) > 0:
            params["tools"] = [_convert_tool_schema(t) for t in tools]

        response = self.client.chat.completions.create(**params)

        choice = response.choices[0]
        message = choice.message

        content = message.content or ""
        tool_calls = _extract_tool_calls(response)
        stop_reason = _map_stop_reason(choice.finish_reason)

        return LLMResponse(
            content=content,
            stop_reason=stop_reason,
            tool_calls=tool_calls,
            usage={
                "input_tokens": response.usage.prompt_tokens,
                "output_tokens": response.usage.completion_tokens
            }
        )
