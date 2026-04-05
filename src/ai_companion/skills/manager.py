"""
Skill manager that discovers and loads skills.
From claw0: External skill discovery from workspace/skills/.
"""

from pathlib import Path
from typing import List, Optional
from ai_companion.types.tool import ToolSchema
from .base import SkillDefinition, load_skill_from_file
from ai_companion.intelligence.builder import PromptBuilderWithSkills


class SkillManager:
    """
    Skill manager discovers skills from workspace/skills/ directory.

    From claw0: Each skill is a directory with a SKILL.md file containing
    frontmatter and skill instructions. Skills are automatically discovered
    and their content injected into the system prompt.
    """

    def __init__(self, workspace_dir: Path):
        self.workspace_dir = workspace_dir
        self.skills_dir = workspace_dir / "skills"
        self._loaded_skills: List[SkillDefinition] = []

    def discover(self) -> List[SkillDefinition]:
        """Discover all skills in the skills directory."""
        skills: List[SkillDefinition] = []

        if not self.skills_dir.exists():
            return skills

        for entry in self.skills_dir.iterdir():
            if entry.is_dir():
                skill_file = entry / "SKILL.md"
                skill = load_skill_from_file(skill_file)
                if skill:
                    skills.append(skill)

        # Sort by priority (lower priority first = higher priority)
        skills.sort(key=lambda s: s.priority)
        self._loaded_skills = skills
        return skills

    def get_tool_schemas(self) -> List[ToolSchema]:
        """Get all loaded skills as tool schemas."""
        from .base import skill_to_tool_schema
        return [skill_to_tool_schema(skill) for skill in self._loaded_skills]

    def assemble_prompt_section(self) -> str:
        """Assemble the skills section of the system prompt."""
        if not self._loaded_skills:
            return ""

        sections = ["## Available Skills\n"]

        for skill in self._loaded_skills:
            sections.append(f"### {skill.name}\n")
            sections.append(f"Description: {skill.description}")
            sections.append(f"Invocation: {skill.invocation}")
            if skill.content:
                sections.append(f"\n{skill.content}\n")

        return "\n".join(sections)

    def inject_into_prompt_builder(self, prompt_builder: PromptBuilderWithSkills) -> None:
        """Inject assembled skills into a prompt builder."""
        prompt_content = self.assemble_prompt_section()
        prompt_builder.set_skills(prompt_content)
