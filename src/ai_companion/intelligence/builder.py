"""
Prompt builder that assembles the system prompt from multiple layers.
From claw0 s06: 8-layer prompt assembly.
"""

from pathlib import Path
from typing import List, Optional
from ai_companion.types.message import Message
from .prompt_layers import PromptLayer, get_default_layers


class PromptBuilder:
    """
    Builds the system prompt by assembling multiple file-based layers.

    From claw0 s06: externalize all prompt engineering to files,
    so changing personality/identity doesn't require code changes.
    """

    def __init__(self, workspace_dir: Path, max_layer_size: int = 10000):
        self.workspace_dir = workspace_dir
        self.max_layer_size = max_layer_size
        self._cached_layers: dict[str, Optional[str]] = {}
        self._layers = get_default_layers(workspace_dir)

    def reload(self) -> None:
        """Reload all layers from disk."""
        self._cached_layers.clear()

    def _read_layer(self, layer: PromptLayer) -> Optional[str]:
        """Read a layer, using cache if already loaded."""
        if layer.name in self._cached_layers:
            return self._cached_layers[layer.name]

        content = layer.read()
        if content is not None and len(content) > self.max_layer_size:
            # Truncate oversized files
            content = content[:self.max_layer_size] + "\n... (truncated)"

        self._cached_layers[layer.name] = content
        return content

    def build_system_prompt(self) -> str:
        """
        Build the complete system prompt by assembling all layers.

        Returns assembled prompt with layer separators for clarity.
        """
        parts: List[str] = []

        for layer in self._layers:
            content = self._read_layer(layer)
            if content is not None and content.strip():
                # Add layer with clear separation
                parts.append(content.strip())

        # Add skills section after loading skills
        # This is handled by SkillManager injecting skills content
        return "\n\n".join(parts)

    def prepare_messages(self, messages: List[Message]) -> List[Message]:
        """
        Prepare messages for the LLM provider.

        For most providers, system prompt is handled separately (passed as system parameter),
        so messages list starts with the first user message.
        """
        # Filter out any system messages - they go in the system prompt
        return [m for m in messages if m.role != "system"]


class PromptBuilderWithSkills(PromptBuilder):
    """Prompt builder that includes skill definitions."""

    def __init__(self, workspace_dir: Path, max_layer_size: int = 10000):
        super().__init__(workspace_dir, max_layer_size)
        self.skills_content: str = ""

    def set_skills(self, skills_content: str) -> None:
        """Set the skills content to be included in the prompt."""
        self.skills_content = skills_content

    def build_system_prompt(self) -> str:
        """Build system prompt including skills section."""
        base = super().build_system_prompt()
        if self.skills_content.strip():
            if base:
                return base + "\n\n" + self.skills_content
            return self.skills_content
        return base
