"""
Plugin manifest parsing.
Adapted from openclaw's plugin manifest format.
"""

import json
from pathlib import Path
from typing import Optional
from pydantic import BaseModel, Field
from ai_companion.types.plugin import PluginManifest as TypedPluginManifest, PluginType


class PluginManifestSchema(BaseModel):
    """Pydantic schema for plugin manifest (ai_companion.plugin.json)."""
    id: str = Field(..., description="Unique plugin identifier")
    name: str = Field(..., description="Human-readable plugin name")
    description: str = Field(..., description="Plugin description")
    version: str = Field(..., description="Semantic version")
    author: str = Field(..., description="Plugin author")
    plugin_type: PluginType = Field(..., description="Type of plugin")
    entry_point: str = Field(..., description="Python entry point (module:class)")
    dependencies: Optional[list[str]] = Field(None, description="Plugin dependencies")
    config_schema: Optional[dict] = Field(None, description="Configuration schema for UI")
    ui_hints: Optional[dict] = Field(None, description="UI hints for configuration")


def load_manifest(plugin_dir: Path) -> Optional[TypedPluginManifest]:
    """Load and parse plugin manifest from ai_companion.plugin.json."""
    manifest_path = plugin_dir / "ai_companion.plugin.json"
    if not manifest_path.exists():
        return None

    try:
        with open(manifest_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        parsed = PluginManifestSchema(**data)

        return TypedPluginManifest(
            id=parsed.id,
            name=parsed.name,
            description=parsed.description,
            version=parsed.version,
            author=parsed.author,
            plugin_type=parsed.plugin_type,
            entry_point=parsed.entry_point,
            dependencies=parsed.dependencies,
            config_schema=parsed.config_schema,
            ui_hints=parsed.ui_hints
        )
    except (json.JSONDecodeError, Exception) as e:
        return None
