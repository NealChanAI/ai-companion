"""
Base plugin interface.
Adapted from openclaw's plugin system.
"""

from abc import ABC, abstractmethod
from typing import Optional
from ai_companion.types.plugin import PluginManifest


class Plugin(ABC):
    """Abstract base class for all plugins."""

    @property
    @abstractmethod
    def manifest(self) -> PluginManifest:
        """Get the plugin manifest."""
        pass

    def initialize(self) -> None:
        """Initialize the plugin after loading. Called once at startup."""
        pass

    def shutdown(self) -> None:
        """Shutdown the plugin. Called when unloading or application exit."""""
        pass
