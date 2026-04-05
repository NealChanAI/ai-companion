"""
Base Channel abstraction.
From claw0 s04 + openclaw: All channels implement the same interface.
"""

from abc import ABC, abstractmethod
from typing import AsyncGenerator, Optional
from ai_companion.types.message import InboundMessage, OutboundMessage


class Channel(ABC):
    """Abstract base class for all messaging channels.

    From claw0 s04: All channels normalize to InboundMessage,
    all sending is via OutboundMessage.
    """

    @property
    @abstractmethod
    def channel_id(self) -> str:
        """Unique identifier for this channel instance."""
        pass

    async def start(self) -> None:
        """Start the channel (e.g., start polling, webhook server)."""
        pass

    async def stop(self) -> None:
        """Stop the channel."""
        pass

    @abstractmethod
    async def receive(self) -> AsyncGenerator[InboundMessage, None]:
        """
        Yield incoming messages from the channel.

        This is async generator that runs until the channel is stopped.
        """
        pass

    @abstractmethod
    async def send(self, message: OutboundMessage) -> bool:
        """
        Send a message through this channel.

        Returns True on success, False on failure.
        """
        pass
