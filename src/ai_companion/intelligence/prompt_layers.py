"""
Prompt layer definitions.
From claw0 s06: 8-layer prompt assembly.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Optional
from ai_companion.utils.file import safe_read_file


@dataclass
class PromptLayer:
    """A single layer in the 8-layer prompt assembly."""
    name: str
    path: Path
    required: bool = False
    description: str = ""

    def read(self) -> Optional[str]:
        """Read the content of this layer."""
        return safe_read_file(self.path)


# The 8-layer assembly order from claw0 s06:
# 1. AGENTS.md - Agent configuration
# 2. TOOLS.md - Tool guidelines
# 3. USER.md - User information
# 4. HEARTBEAT.md - Proactive messaging instructions
# 5. BOOTSTRAP.md - Bootstrap instructions
# 6. MEMORY.md - Long-term user memory
# 7. SOUL.md + IDENTITY.md - Personality and core identity
# 8. Skills - Skill definitions

def get_default_layers(workspace_dir: Path) -> list[PromptLayer]:
    """Get the default 8-layer prompt assembly in order.

    From claw0 s06: specific ordering matters - later layers don't override earlier,
    but the model pays more attention to the end of the prompt.
    """
    return [
        PromptLayer("agents", workspace_dir / "AGENTS.md", False, "Agent configuration"),
        PromptLayer("tools", workspace_dir / "TOOLS.md", False, "Tool usage guidelines"),
        PromptLayer("user", workspace_dir / "USER.md", False, "User information"),
        PromptLayer("heartbeat", workspace_dir / "HEARTBEAT.md", False, "Proactive messaging instructions"),
        PromptLayer("bootstrap", workspace_dir / "BOOTSTRAP.md", False, "Bootstrap instructions"),
        PromptLayer("memory", workspace_dir / "MEMORY.md", False, "Long-term memory"),
        PromptLayer("identity", workspace_dir / "IDENTITY.md", True, "Core identity"),
        PromptLayer("soul", workspace_dir / "SOUL.md", True, "Personality"),
    ]
