"""
Core agent loop.
From claw0 s01: while True + stop_reason pattern.
"""

import logging
from typing import List, Optional, Callable
from ai_companion.types.message import Message
from ai_companion.types.tool import ToolSchema, ToolCall, ToolResult
from ai_companion.types.session import Session
from ai_companion.providers.base import BaseProvider
from ai_companion.intelligence.builder import PromptBuilder
from .stop_reason import is_turn_complete
from .turn import TurnResult

logger = logging.getLogger(__name__)


class AgentLoop:
    """
    Core agent loop implementing the while True + stop_reason pattern from claw0.

    Flow:
    1. Add user input to messages
    2. Call LLM
    3. Check stop_reason:
       - end_turn → respond to user, turn complete
       - tool_use → execute tools, add results, repeat
    """

    def __init__(
        self,
        provider: BaseProvider,
        prompt_builder: PromptBuilder,
        tools: List[ToolSchema] | None = None
    ):
        self.provider = provider
        self.prompt_builder = prompt_builder
        self.tools = tools or []
        self.max_tool_iterations = 10

    def run_turn(
        self,
        session: Session,
        tool_executor: Callable[[ToolCall], ToolResult]
    ) -> TurnResult:
        """
        Run a single turn starting from the last user message.

        Args:
            session: Current session with messages
            tool_executor: Function to execute a tool call

        Returns:
            TurnResult with messages added and whether the turn is complete
        """
        messages_added: List[Message] = []
        tool_calls_this_turn: List[ToolCall] = []
        assistant_response: Optional[str] = None

        system_prompt = self.prompt_builder.build_system_prompt()
        messages = self.prompt_builder.prepare_messages(session.messages)

        logger.info(f"[AGENT LOOP] Starting new turn, {len(messages)} messages in context")
        logger.info(f"[LLM INPUT] System prompt length: {len(system_prompt)} chars")
        if len(system_prompt) <= 1000:
            logger.info(f"[LLM INPUT] Full system prompt:\n{system_prompt}")
        else:
            logger.info(f"[LLM INPUT] System prompt (truncated):\n{system_prompt[:1000]}...")

        # Log all messages
        for i, msg in enumerate(messages):  # Log all messages for full context
            if isinstance(msg.content, str):
                logger.info(f"[LLM INPUT] Message {i} {msg.role}: {repr(msg.content)}")
            else:
                logger.info(f"[LLM INPUT] Message {i} {msg.role}: ({type(msg.content).__name__}) {len(msg.content)} blocks")

        iterations = 0
        while iterations < self.max_tool_iterations:
            iterations += 1
            logger.info(f"[AGENT LOOP] LLM call #{iterations}/{self.max_tool_iterations}")
            logger.info(f"[LLM INPUT FULL] System prompt:\n{repr(system_prompt)}")
            logger.info(f"[LLM INPUT FULL] Messages ({len(messages)} total):")
            for i, msg in enumerate(messages):
                if isinstance(msg.content, str):
                    logger.info(f"[LLM INPUT FULL] Message {i} {msg.role}:\n{repr(msg.content)}")
                else:
                    logger.info(f"[LLM INPUT FULL] Message {i} {msg.role}: ({type(msg.content).__name__}) {len(msg.content)} blocks")

            response = self.provider.complete(
                messages=messages,
                system_prompt=system_prompt,
                tools=self.tools if self.tools else None
            )

            # Log LLM output for debugging
            if isinstance(response.content, str):
                logger.info(f"[LLM OUTPUT #{iterations}] Content:\n{repr(response.content)}")
            else:
                logger.info(f"[LLM OUTPUT #{iterations}] ({len(response.content)} content blocks) stop_reason={response.stop_reason}")
                for idx, block in enumerate(response.content):
                    logger.info(f"[LLM OUTPUT #{iterations}] Block {idx} full: {repr(block)}")

            if response.tool_calls:
                logger.info(f"[LLM OUTPUT #{iterations}] {len(response.tool_calls)} tool call(s):")
                for tc in response.tool_calls:
                    logger.info(f"  - {tc.tool_name}: parameters={repr(tc.parameters)}")

            # Convert response to message
            if isinstance(response.content, str):
                assistant_msg = Message(
                    role="assistant",
                    content=response.content
                )
                if response.stop_reason != "tool_use" and not assistant_response:
                    assistant_response = response.content
            else:
                # Content is a list of blocks (thinking mode or tool use)
                assistant_msg = Message(
                    role="assistant",
                    content=response.content
                )
                # Extract text content from blocks for assistant_response
                if response.stop_reason != "tool_use" and not assistant_response:
                    text_content = ""
                    for block in response.content:
                        block_type = block.get('type', '')
                        if block_type == 'text':
                            text = block.get('text', '')
                            text_content += text
                        elif block_type == 'thinking':
                            # Skip thinking blocks in response
                            continue
                    if text_content:
                        assistant_response = text_content

            messages.append(assistant_msg)
            messages_added.append(assistant_msg)
            tool_calls_this_turn.extend(response.tool_calls)

            complete = is_turn_complete(response.stop_reason)
            if complete:
                # Turn is complete
                logger.info(f"[AGENT LOOP] Turn complete after {iterations} LLM call(s), {len(tool_calls_this_turn)} tool call(s)")
                return TurnResult(
                    messages_added=messages_added,
                    assistant_response=assistant_response,
                    stop_reason=response.stop_reason,
                    tool_calls=tool_calls_this_turn,
                    complete=True
                )

            # We have tool calls to execute
            logger.info(f"[AGENT LOOP] Executing {len(response.tool_calls)} tool call(s)")
            for tool_call in response.tool_calls:
                logger.info(f"[TOOL EXECUTE] Calling {tool_call.tool_name}, parameters={repr(tool_call.parameters)}")
                result = tool_executor(tool_call)
                logger.info(f"[TOOL RESULT] {tool_call.tool_name} success={result.success}, output={repr(result.content[:500])}{'...' if len(result.content) > 500 else ''}")
                tool_result_msg = Message(
                    role="user",
                    content=result.content,
                    metadata={
                        "tool_call_id": result.tool_call_id,
                        "tool_name": result.tool_name,
                        "is_tool_result": True,
                        "success": result.success
                    }
                )
                messages.append(tool_result_msg)
                messages_added.append(tool_result_msg)

        # Hit max iterations - return anyway
        logger.warning(f"[AGENT LOOP] Hit max {self.max_tool_iterations} iterations, stopping")
        return TurnResult(
            messages_added=messages_added,
            assistant_response=assistant_response,
            stop_reason="max_tokens",
            tool_calls=tool_calls_this_turn,
            complete=True
        )
