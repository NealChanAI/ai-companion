"""
Message type definitions.
Inspired by claw0's unified message model.
"""

from dataclasses import dataclass
from typing import Optional, Literal


@dataclass
class Message:
    """A message in the conversation history."""
    role: Literal["user", "assistant", "system", "tool"]
    content: str | list[dict]
    metadata: dict | None = None


@dataclass
class InboundMessage:
    """Unified inbound message from any channel.

    All channels normalize incoming messages to this format.
    Inspired by claw0's InboundMessage pattern.
    """
    channel_id: str
    peer_id: str  # User/chat identifier
    content: str
    message_id: str
    timestamp: int
    metadata: dict | None = None

    @property
    def routing_key(self) -> tuple[str, str]:
        """Routing key for 5-tier routing: (channel_id, peer_id)"""
        return (self.channel_id, self.peer_id)


@dataclass
class OutboundMessage:
    """Outbound message to be sent to a channel."""
    target_channel: str
    target_peer: str
    content: str
    metadata: dict | None = None
