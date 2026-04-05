"""
Built-in memory writing skill.
When the assistant identifies important information to remember long-term,
it writes it to MEMORY.md.
"""

from pathlib import Path
from typing import Optional
from ai_companion.types.tool import ToolCall, ToolResult
from ai_companion.utils.file import safe_read_file, safe_write_file


class MemorySkill:
    """Built-in skill for writing long-term memory to MEMORY.md."""

    def __init__(self, workspace_dir: Path):
        self.memory_path = workspace_dir / "MEMORY.md"

    def read_memory(self) -> str:
        """Read current memory content."""
        content = safe_read_file(self.memory_path)
        return content or ""

    def append_memory(self, entry: str) -> bool:
        """Append an entry to memory."""
        current = self.read_memory()
        # Find the last empty line and add the bullet point
        lines = current.rstrip().splitlines()
        while lines and not lines[-1].strip():
            lines.pop()
        lines.append(f"- {entry}")
        new_content = "\n".join(lines) + "\n"
        return safe_write_file(self.memory_path, new_content)

    def remove_entry(self, entry: str) -> bool:
        """Remove an entry from memory (approximate match)."""
        current = self.read_memory()
        lines = current.splitlines()
        new_lines = [
            line for line in lines
            if entry.lower() not in line.lower() or not line.strip().startswith("- ")
        ]
        new_content = "\n".join(new_lines) + "\n"
        return safe_write_file(self.memory_path, new_content)

    def execute(self, tool_call: ToolCall) -> ToolResult:
        """Execute the memory skill."""
        action = tool_call.parameters.get("action", "append")
        content = tool_call.parameters.get("content", "")

        if action == "append":
            success = self.append_memory(content)
            if success:
                return ToolResult(
                    tool_name="memory-write",
                    tool_call_id=tool_call.tool_call_id,
                    content=f"Successfully wrote to memory: {content}",
                    success=True
                )
            else:
                return ToolResult(
                    tool_name="memory-write",
                    tool_call_id=tool_call.tool_call_id,
                    content=f"Failed to write to memory",
                    success=False
                )
        elif action == "remove":
            success = self.remove_entry(content)
            return ToolResult(
                tool_name="memory-write",
                tool_call_id=tool_call.tool_call_id,
                content=f"Removed entries matching: {content}",
                success=success
            )
        else:
            return ToolResult(
                tool_name="memory-write",
                tool_call_id=tool_call.tool_call_id,
                content=f"Unknown action: {action}",
                success=False
            )
