"""
Configuration loader.
Adapted from openclaw's hierarchical config loading.
"""

import os
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv
from .schema import AppConfig


def find_env_file(start_path: Optional[Path] = None) -> Optional[Path]:
    """Find the .env file starting from the current directory going up."""
    if start_path is None:
        start_path = Path.cwd()

    current = start_path
    while current != current.parent:
        candidate = current / ".env"
        if candidate.exists():
            return candidate
        current = current.parent

    return None


def load_config(env_path: Optional[Path] = None) -> AppConfig:
    """Load configuration from environment and .env file.

    Follows openclaw's hierarchical loading:
    1. Environment variables override everything
    2. .env file
    3. Default values
    """
    if env_path is None:
        env_path = find_env_file()

    if env_path is not None and env_path.exists():
        load_dotenv(env_path)

    config = AppConfig()

    # Ensure directories exist
    config.workspace_dir.mkdir(exist_ok=True, parents=True)
    config.sessions_dir.mkdir(exist_ok=True, parents=True)
    config.plugins_dir.mkdir(exist_ok=True, parents=True)

    return config


def validate_config(config: AppConfig) -> list[str]:
    """Validate configuration and return list of errors.

    Returns empty list if configuration is valid.
    """
    errors = []

    if config.default_provider == "anthropic" and not config.anthropic_api_key:
        errors.append("ANTHROPIC_API_KEY is required when default_provider is anthropic")

    if config.default_provider == "openai" and not config.openai_api_key:
        errors.append("OPENAI_API_KEY is required when default_provider is openai")

    if not config.workspace_dir.exists():
        errors.append(f"Workspace directory {config.workspace_dir} does not exist")

    return errors
