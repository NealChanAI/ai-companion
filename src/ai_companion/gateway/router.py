"""
Gateway router that routes inbound messages to the correct agent session.
From claw0 s05: 5-tier routing.
"""

from typing import Optional
from ai_companion.types.message import InboundMessage
from ai_companion.types.session import Session
from ai_companion.sessions.store import SessionStore
from .binding import BindingTable


class GatewayRouter:
    """
    Gateway router that routes messages to the correct agent session.

    From claw0 s05: 5-tier binding table with most-specific-first matching.
    """

    def __init__(
        self,
        binding_table: BindingTable,
        session_store: SessionStore
    ):
        self.binding_table = binding_table
        self.session_store = session_store

    def route(self, message: InboundMessage) -> Session:
        """
        Route an inbound message to the appropriate session, creating one if needed.

        Uses 5-tier binding to find the correct agent, then gets or creates
        the session for (channel_id, peer_id, agent_id).
        """
        # Resolve which agent this goes to using 5-tier binding
        agent_id = self.binding_table.resolve(
            channel_id=message.channel_id,
            peer_id=message.peer_id
        )

        # Get or create session
        session = self.session_store.get_or_create(
            agent_id=agent_id,
            channel_id=message.channel_id,
            peer_id=message.peer_id
        )

        return session
