"""
Built-in weather query skill.
Get current weather and forecasts via wttr.in.
"""

import subprocess
from typing import Optional
from ai_companion.types.tool import ToolCall, ToolResult


class WeatherSkill:
    """Built-in skill for querying weather from wttr.in."""

    def execute(self, tool_call: ToolCall) -> ToolResult:
        """Execute the weather skill."""
        city = tool_call.parameters.get("city", "").strip()
        if not city:
            return ToolResult(
                tool_name="weather",
                tool_call_id=tool_call.tool_call_id,
                content="Error: city parameter is required",
                success=False
            )

        # URL encode the city (replace space with +)
        city_encoded = city.replace(" ", "+")

        # Build the curl command for one-line summary
        cmd = (
            f'curl -s "wttr.in/{city_encoded}?format=%l:+%c+%t+(feels+like+%f),+%w+wind,+%h+humidity"'
        )

        try:
            result = subprocess.run(
                cmd,
                shell=True,
                capture_output=True,
                text=True,
                timeout=10
            )

            if result.returncode != 0:
                return ToolResult(
                    tool_name="weather",
                    tool_call_id=tool_call.tool_call_id,
                    content=f"Failed to get weather: {result.stderr}",
                    success=False
                )

            output = result.stdout.strip()
            if not output:
                return ToolResult(
                    tool_name="weather",
                    tool_call_id=tool_call.tool_call_id,
                    content="Empty response from weather service",
                    success=False
                )

            return ToolResult(
                tool_name="weather",
                tool_call_id=tool_call.tool_call_id,
                content=output,
                success=True
            )

        except subprocess.TimeoutExpired:
            return ToolResult(
                tool_name="weather",
                tool_call_id=tool_call.tool_call_id,
                content="Request timed out",
                success=False
            )
        except Exception as e:
            return ToolResult(
                tool_name="weather",
                tool_call_id=tool_call.tool_call_id,
                content=f"Error: {str(e)}",
                success=False
            )
