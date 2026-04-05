"""
Write-ahead queue for guaranteed message delivery.
From claw0 s08: All messages go through WAL before sending,
so they survive crashes and can be retried.
"""

import json
import time
from pathlib import Path
from typing import Optional, List
from dataclasses import dataclass
from ai_companion.types.message import OutboundMessage
from ai_companion.utils.file import atomic_write
from .backoff import calculate_backoff


@dataclass
class QueuedMessage:
    """A queued outbound message."""
    id: str
    message: OutboundMessage
    created_at: int
    attempts: int
    next_attempt_at: int
    last_error: Optional[str] = None


class WriteAheadQueue:
    """
    Write-ahead queue for guaranteed message delivery.

    From claw0 s08: All outbound messages are written to disk first,
    then sent. If sending fails, they are retried with exponential backoff.
    Permanently failed messages go to failed/ directory.
    """

    def __init__(self, queue_dir: Path, max_attempts: int = 4):
        self.queue_dir = queue_dir
        self.max_attempts = max_attempts
        self.pending_dir = queue_dir / "pending"
        self.failed_dir = queue_dir / "failed"
        self.pending_dir.mkdir(parents=True, exist_ok=True)
        self.failed_dir.mkdir(parents=True, exist_ok=True)

    def enqueue(self, message: OutboundMessage, message_id: str) -> QueuedMessage:
        """Enqueue a message for sending."""
        now = int(time.time())
        queued = QueuedMessage(
            id=message_id,
            message=message,
            created_at=now,
            attempts=0,
            next_attempt_at=now
        )
        self._save(queued)
        return queued

    def _save(self, queued: QueuedMessage) -> None:
        """Save queued message to disk."""
        path = self.pending_dir / f"{queued.id}.json"
        data = {
            "id": queued.id,
            "message": {
                "target_channel": queued.message.target_channel,
                "target_peer": queued.message.target_peer,
                "content": queued.message.content,
                "metadata": queued.message.metadata
            },
            "created_at": queued.created_at,
            "attempts": queued.attempts,
            "next_attempt_at": queued.next_attempt_at,
            "last_error": queued.last_error
        }
        with atomic_write(path, "w") as f:
            json.dump(data, f, indent=2)

    def _remove(self, message_id: str) -> None:
        """Remove a successfully sent message from the queue."""
        path = self.pending_dir / f"{message_id}.json"
        if path.exists():
            path.unlink()

    def _move_to_failed(self, queued: QueuedMessage) -> None:
        """Move a permanently failed message to failed directory."""
        source = self.pending_dir / f"{queued.id}.json"
        dest = self.failed_dir / f"{queued.id}.json"
        if source.exists():
            data = json.loads(source.read_text())
            with open(dest, 'w') as f:
                json.dump(data, f, indent=2)
            source.unlink()

    def mark_success(self, message_id: str) -> None:
        """Mark a message as successfully sent."""
        self._remove(message_id)

    def mark_failed(self, queued: QueuedMessage, error: str) -> bool:
        """
        Mark a send attempt as failed.
        Returns True if should retry, False if permanently failed.
        """
        queued.attempts += 1
        queued.last_error = error

        if queued.attempts >= self.max_attempts:
            self._move_to_failed(queued)
            return False

        # Calculate next attempt time with exponential backoff
        delay = calculate_backoff(queued.attempts)
        queued.next_attempt_at = int(time.time()) + delay
        self._save(queued)
        return True

    def get_ready(self) -> List[QueuedMessage]:
        """Get all messages ready for sending."""
        now = int(time.time())
        ready: List[QueuedMessage] = []

        for json_file in self.pending_dir.glob("*.json"):
            try:
                data = json.loads(json_file.read_text())
                queued = QueuedMessage(
                    id=data["id"],
                    message=OutboundMessage(**data["message"]),
                    created_at=data["created_at"],
                    attempts=data["attempts"],
                    next_attempt_at=data["next_attempt_at"],
                    last_error=data.get("last_error")
                )
                if queued.next_attempt_at <= now:
                    ready.append(queued)
            except Exception:
                # Skip corrupted messages
                continue

        return ready

    def load_pending(self) -> List[QueuedMessage]:
        """Load all pending messages."""
        pending: List[QueuedMessage] = []
        for json_file in self.pending_dir.glob("*.json"):
            try:
                data = json.loads(json_file.read_text())
                queued = QueuedMessage(
                    id=data["id"],
                    message=OutboundMessage(**data["message"]),
                    created_at=data["created_at"],
                    attempts=data["attempts"],
                    next_attempt_at=data["next_attempt_at"],
                    last_error=data.get("last_error")
                )
                pending.append(queued)
            except Exception:
                continue
        return pending
