"""
5-tier binding table for routing.
From claw0 s05: 5-tier binding table, most-specific matching wins.

Tiers (from most specific to least):
1. Tier 1: Peer ID - specific user to specific agent
2. Tier 2: Guild/Workspace ID - guild/workspace to specific agent
3. Tier 3: Account ID - bot account to specific agent
4. Tier 4: Channel - entire channel type to specific agent
5. Tier 5: Default - fallback default agent
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class Binding:
    """A single routing binding."""
    tier: int  # 1-5, lower is more specific
    channel_id: Optional[str] = None
    guild_id: Optional[str] = None
    account_id: Optional[str] = None
    peer_id: Optional[str] = None
    agent_id: str = "companion"

    def matches(
        self,
        channel_id: str,
        peer_id: str,
        guild_id: Optional[str] = None,
        account_id: Optional[str] = None
    ) -> bool:
        """Check if this binding matches the given routing key."""
        if self.channel_id is not None and self.channel_id != channel_id:
            return False
        if self.guild_id is not None and self.guild_id != guild_id:
            return False
        if self.account_id is not None and self.account_id != account_id:
            return False
        if self.peer_id is not None and self.peer_id != peer_id:
            return False
        return True


class BindingTable:
    """
    5-tier binding table for routing.
    From claw0 s05: Most specific match always wins.
    """

    def __init__(self):
        self.bindings: list[Binding] = []
        # Add default binding at tier 5
        self.bindings.append(Binding(tier=5, agent_id="companion"))

    def add_binding(self, binding: Binding) -> None:
        """Add a binding. Bindings are kept sorted by specificity (most specific first)."""
        self.bindings.append(binding)
        # Sort by tier (lower tier = more specific)
        self.bindings.sort(key=lambda b: b.tier)

    def resolve(
        self,
        channel_id: str,
        peer_id: str,
        guild_id: Optional[str] = None,
        account_id: Optional[str] = None
    ) -> str:
        """
        Resolve the routing key to an agent_id.
        Returns the most specific matching binding's agent_id.
        """
        for binding in self.bindings:
            if binding.matches(channel_id, peer_id, guild_id, account_id):
                return binding.agent_id

        # Default binding should always match
        return "companion"

    def load_from_agents_file(self, content: str) -> None:
        """Load bindings from AGENTS.md file."""
        # Simple parser - look for yaml-style agent definitions
        # This is a basic implementation that creates a channel-level binding
        lines = content.splitlines()
        in_list = False

        for line in lines:
            line = line.strip()
            if line.startswith("- agent_id:"):
                in_list = True
                agent_id = line.split(":", 1)[1].strip()
                current = {"agent_id": agent_id}
                continue

            if in_list and line.startswith("channel_id:"):
                current["channel_id"] = line.split(":", 1)[1].strip()
            elif in_list and line.startswith("peer_id:"):
                current["peer_id"] = line.split(":", 1)[1].strip()
            elif in_list and line.startswith("workspace_path:"):
                # Just store for reference, binding doesn't need it
                pass
            elif line == "" and in_list:
                # End of entry, create binding
                tier = self._tier_for_binding(current)
                binding = Binding(
                    tier=tier,
                    channel_id=current.get("channel_id"),
                    peer_id=current.get("peer_id"),
                    agent_id=current.get("agent_id", "companion")
                )
                self.add_binding(binding)
                in_list = False

    def _tier_for_binding(self, binding_dict: dict) -> int:
        """Determine the tier based on what fields are set."""
        if "peer_id" in binding_dict and binding_dict["peer_id"]:
            return 1
        if "guild_id" in binding_dict and binding_dict["guild_id"]:
            return 2
        if "account_id" in binding_dict and binding_dict["account_id"]:
            return 3
        if "channel_id" in binding_dict and binding_dict["channel_id"]:
            return 4
        return 5
