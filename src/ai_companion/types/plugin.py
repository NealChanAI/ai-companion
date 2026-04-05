"""
Plugin type definitions.
Adapted from openclaw's plugin manifest pattern.
"""

from dataclasses import dataclass
from typing import Optional, Dict, Any, Literal


PluginType = Literal["channel", "provider", "skill", "memory"]


@dataclass
class PluginManifest:
    """Plugin manifest metadata.

    Adapted from openclaw's openclaw.plugin.json format.
    """
    id: str
    name: str
    description: str
    version: str
    author: str
    plugin_type: PluginType
    entry_point: str
    dependencies: list[str] | None = None
    config_schema: dict[str, Any] | None = None
    ui_hints: dict[str, Any] | None = None


@dataclass
class LoadedPlugin:
    """A loaded plugin instance."""
    manifest: PluginManifest
    module: Any
    instance: Any
    path: str
