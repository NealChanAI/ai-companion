"""
Bootstrap loader for loading prompt layers on startup.
From claw0 s06: bootstrap process.
"""

from pathlib import Path
from .builder import PromptBuilder


def bootstrap_prompt_builder(workspace_dir: Path) -> PromptBuilder:
    """
    Bootstrap a prompt builder, loading all layers from the workspace.

    From claw0 s06: bootstrap step that reads all the prompt files.
    """
    builder = PromptBuilder(workspace_dir)
    # Trigger cache loading
    builder.build_system_prompt()
    return builder
