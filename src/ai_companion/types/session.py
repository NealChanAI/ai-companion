"""
Session type definitions.
Inspired by claw0's JSONL session persistence.
"""

from dataclasses import dataclass
from typing import Optional, List
from .message import Message


@dataclass
class SessionMetadata:
    """Metadata for a session."""
    session_id: str
    agent_id: str
    channel_id: str
    peer_id: str
    started_at: int
    last_active: int
    message_count: int = 0
    metadata: dict | None = None


@dataclass
class Session:
    """A conversation session."""
    metadata: SessionMetadata
    messages: List[Message]

    @property
    def session_id(self) -> str:
        return self.metadata.session_id

    @property
    def is_empty(self) -> bool:
        return len(self.messages) == 0
