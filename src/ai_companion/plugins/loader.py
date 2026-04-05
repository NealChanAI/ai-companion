"""
Plugin loader that discovers and loads plugins.
Adapted from openclaw's plugin discovery.
"""

import importlib
import sys
from pathlib import Path
from typing import List, List
from ai_companion.types.plugin import LoadedPlugin, PluginManifest
from .manifest import load_manifest
from .registry import PluginRegistry
from ai_companion.logging.logger import get_logger


logger = get_logger(__name__)


def import_module_from_path(module_name: str, path: Path) -> any:
    """Import a module from a file system path."""
    # Add the parent directory to sys.path
    if str(path.parent) not in sys.path:
        sys.path.insert(0, str(path.parent))

    return importlib.import_module(module_name)


class PluginLoader:
    """
    Plugin loader that discovers plugins in a directory and loads them.

    Adapted from openclaw's plugin discovery pattern.
    """

    def __init__(self, plugins_dir: Path, registry: PluginRegistry):
        self.plugins_dir = plugins_dir
        self.registry = registry

    def discover(self) -> List[PluginManifest]:
        """Discover all plugins in the plugins directory."""
        manifests: List[PluginManifest] = []

        if not self.plugins_dir.exists():
            return manifests

        for entry in self.plugins_dir.iterdir():
            if entry.is_dir():
                manifest = load_manifest(entry)
                if manifest:
                    manifests.append(manifest)

        return manifests

    def load_plugin(self, plugin_dir: Path, manifest: PluginManifest) -> LoadedPlugin | None:
        """Load a single plugin."""
        try:
            # Parse entry point: module.class or module.function
            module_path = entry_point = manifest.entry_point
            if ':' in entry_point:
                module_name, class_name = entry_point.split(':', 1)
            else:
                module_name = entry_point
                class_name = None

            # Import the module
            module = import_module_from_path(module_name, plugin_dir / module_name.replace('.', '/') + '.py')

            if class_name:
                instance = getattr(module, class_name)()
            else:
                instance = module

            loaded = LoadedPlugin(
                manifest=manifest,
                module=module,
                instance=instance,
                path=str(plugin_dir)
            )

            # Call initialize if plugin has it
            if hasattr(instance, 'initialize') and callable(instance.initialize):
                instance.initialize()

            self.registry.register(loaded)
            logger.info(f"Loaded plugin: {manifest.name} ({manifest.id})")
            return loaded

        except Exception as e:
            logger.error(f"Failed to load plugin {manifest.id}: {e}")
            return None

    def load_all_discovered(self) -> List[LoadedPlugin]:
        """Discover and load all plugins."""
        loaded: List[LoadedPlugin] = []
        manifests = self.discover()
        for manifest in manifests:
            plugin_dir = self.plugins_dir / manifest.id
            loaded_plugin = self.load_plugin(plugin_dir, manifest)
            if loaded_plugin:
                loaded.append(loaded_plugin)
        return loaded
