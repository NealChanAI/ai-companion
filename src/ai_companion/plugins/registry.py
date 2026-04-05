"""
Plugin registry that holds loaded plugins.
Adapted from openclaw's plugin registry.
"""

from typing import Dict, Optional, List
from ai_companion.types.plugin import LoadedPlugin


class PluginRegistry:
    """Registry for loaded plugins."""

    def __init__(self):
        self._plugins: Dict[str, LoadedPlugin] = {}

    def register(self, plugin: LoadedPlugin) -> None:
        """Register a loaded plugin."""
        self._plugins[plugin.manifest.id] = plugin

    def get(self, plugin_id: str) -> Optional[LoadedPlugin]:
        """Get a plugin by ID."""
        return self._plugins.get(plugin_id)

    def list_plugins(self) -> List[LoadedPlugin]:
        """List all loaded plugins."""
        return list(self._plugins.values())

    def list_by_type(self, plugin_type: str) -> List[LoadedPlugin]:
        """List plugins of a specific type."""
        return [
            p for p in self._plugins.values()
            if p.manifest.plugin_type == plugin_type
        ]

    def unregister(self, plugin_id: str) -> bool:
        """Unregister a plugin."""
        if plugin_id in self._plugins:
            del self._plugins[plugin_id]
            return True
        return False
