"""
Base skill interface.
From claw0: external skill definitions in SKILL.md.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Optional
import frontmatter  # python-frontmatter
from ai_companion.types.tool import ToolSchema


@dataclass
class SkillDefinition:
    """Skill definition from SKILL.md frontmatter."""
    name: str
    description: str
    invocation: str  # "auto" for automatic use, or command pattern
    priority: int = 10
    content: str = ""  # The markdown content of the skill
    path: Path | None = None


def load_skill_from_file(path: Path) -> Optional[SkillDefinition]:
    """Load a skill definition from a SKILL.md file with frontmatter.

    From claw0: Each skill is a directory with a SKILL.md that has
    frontmatter metadata.
    """
    if not path.exists():
        return None

    try:
        post = frontmatter.load(path)
        return SkillDefinition(
            name=post.metadata.get("name", path.parent.name),
            description=post.metadata.get("description", ""),
            invocation=post.metadata.get("invocation", "auto"),
            priority=post.metadata.get("priority", 10),
            content=post.content.strip(),
            path=path
        )
    except Exception:
        return None


def skill_to_tool_schema(definition: SkillDefinition) -> ToolSchema:
    """Convert a skill definition to tool schema."""
    # For weather skill, we know it needs city parameter
    from ai_companion.types.tool import ToolParameter
    if definition.name == "weather":
        parameters = [
            ToolParameter(
                name="city",
                type="string",
                description="要查询天气的城市名称"
            )
        ]
    else:
        parameters = []

    return ToolSchema(
        name=definition.name.replace(" ", "-"),
        description=definition.description + "\n\n" + definition.content,
        parameters=parameters
    )
