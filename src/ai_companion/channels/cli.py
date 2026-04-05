"""
CLI (Command Line Interface) channel.
"""

import asyncio
import sys
import time
import uuid
from typing import AsyncGenerator
from ai_companion.types.message import InboundMessage, OutboundMessage
from .base import Channel


class CliChannel(Channel):
    """Command-line interface channel for interactive testing."""

    def __init__(self, prompt: str = "You> "):
        self._channel_id = "cli"
        self._prompt = prompt
        self._running = False

    @property
    def channel_id(self) -> str:
        return self._channel_id

    async def start(self) -> None:
        self._running = True

    async def stop(self) -> None:
        self._running = False

    async def receive(self) -> AsyncGenerator[InboundMessage, None]:
        """Yield user input from stdin."""
        while self._running:
            # Read line asynchronously
            try:
                line = await self._read_line()
                if not line:
                    continue

                if line.strip().lower() in ("/quit", "/exit", "quit", "exit"):
                    self._running = False
                    break

                yield InboundMessage(
                    channel_id=self.channel_id,
                    peer_id="cli-user",
                    content=line,
                    message_id=str(uuid.uuid4()),
                    timestamp=int(time.time())
                )
            except (EOFError, KeyboardInterrupt):
                self._running = False
                break

    async def _read_line(self) -> str:
        """Read a line from stdin asynchronously."""
        loop = asyncio.get_event_loop()
        print(self._prompt, end='', flush=True)
        return await loop.run_in_executor(None, sys.stdin.readline)

    async def send(self, message: OutboundMessage) -> bool:
        """Print the message to stdout."""
        try:
            print(f"\nAI> {message.content}\n")
            return True
        except Exception:
            return False
