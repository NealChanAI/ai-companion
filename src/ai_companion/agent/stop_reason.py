"""
Stop reason definitions and handling.
From claw0 s01: stop_reason pattern.
"""

from typing import Literal


StopReason = Literal["end_turn", "tool_use", "max_tokens", "stop_sequence"]


def is_turn_complete(stop_reason: StopReason) -> bool:
    """Check if the current turn is complete and we can respond to the user.

    From claw0 s01 pattern:
    - end_turn → respond to user
    - tool_use → continue with tool execution
    - max_tokens/stop_sequence → incomplete, but we'll respond with what we have
    """
    match stop_reason:
        case "end_turn":
            return True
        case "tool_use":
            return False
        case "max_tokens" | "stop_sequence":
            return True
