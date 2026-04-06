"""
Pydantic configuration schema for AI Companion.
Adapted from openclaw's config schema pattern.
"""

from pydantic import Field
from pydantic_settings import BaseSettings
from typing import Optional, Dict, List, Tuple
from pathlib import Path
from .heartbeat import HeartbeatConfig
from .cron import CronConfig


class AppConfig(BaseSettings):
    """Top-level application configuration.

    Follows openclaw's hierarchical configuration pattern.
    Configuration precedence: environment variables > .env > defaults
    """
    # Provider config (top-level for easy environment mapping)
    default_provider: str = Field("anthropic", validation_alias="DEFAULT_PROVIDER")
    default_model: str = Field("claude-3-5-sonnet-20241022", validation_alias="DEFAULT_MODEL")
    anthropic_api_key: Optional[str] = Field(None, validation_alias="ANTHROPIC_API_KEY")
    anthropic_base_url: Optional[str] = Field(None, validation_alias="ANTHROPIC_BASE_URL")
    openai_api_key: Optional[str] = Field(None, validation_alias="OPENAI_API_KEY")
    openai_base_url: Optional[str] = Field(None, validation_alias="OPENAI_BASE_URL")
    max_tokens: int = Field(4096, validation_alias="MAX_TOKENS")
    temperature: float = Field(0.7, validation_alias="TEMPERATURE")

    # Feishu config
    feishu_app_id: Optional[str] = Field(None, validation_alias="FEISHU_APP_ID")
    feishu_app_secret: Optional[str] = Field(None, validation_alias="FEISHU_APP_SECRET")
    feishu_webhook_url: Optional[str] = Field(None, validation_alias="FEISHU_WEBHOOK_URL")
    feishu_verification_token: Optional[str] = Field(None, validation_alias="FEISHU_VERIFICATION_TOKEN")
    feishu_encrypt_key: Optional[str] = Field(None, validation_alias="FEISHU_ENCRYPT_KEY")

    # Server config
    host: str = Field("0.0.0.0", validation_alias="HOST")
    port: int = Field(8080, validation_alias="PORT")
    debug: bool = Field(False, validation_alias="DEBUG")

    # Paths config
    workspace_dir: Path = Field(Path("./workspace"), validation_alias="WORKSPACE_DIR")
    sessions_dir: Path = Field(Path("./sessions"), validation_alias="SESSIONS_DIR")
    plugins_dir: Path = Field(Path("./plugins"), validation_alias="PLUGINS_DIR")

    # Agent config
    default_agent_id: str = "companion"
    max_context_tokens: int = Field(100000, validation_alias="MAX_CONTEXT_TOKENS")
    enable_compression: bool = Field(True, validation_alias="ENABLE_COMPRESSION")

    # Logging config
    log_level: str = Field("INFO", validation_alias="LOG_LEVEL")
    log_file: Optional[Path] = Field(None, validation_alias="LOG_FILE")

    # Heartbeat and cron configs
    # Use Field with validation_alias but without default_factory
    # to allow environment variable overrides
    heartbeat: HeartbeatConfig = Field(default=HeartbeatConfig())
    cron: CronConfig = Field(default=CronConfig())

    # Paths for heartbeat and cron
    heartbeat_file: Path = Field(
        default=Path("HEARTBEAT.md"),
        validation_alias="HEARTBEAT_FILE"
    )
    cron_file: Path = Field(
        default=Path("CRON.json"),
        validation_alias="CRON_FILE"
    )

    class Config:
        env_file = ".env"
        case_sensitive = False
        extra = "allow"

    # Helper to get provider config as a dict for construction
    def get_provider_config(self) -> dict:
        return {
            "default_provider": self.default_provider,
            "default_model": self.default_model,
            "anthropic_api_key": self.anthropic_api_key,
            "anthropic_base_url": self.anthropic_base_url,
            "openai_api_key": self.openai_api_key,
            "openai_base_url": self.openai_base_url,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
        }

    def get_feishu_config(self) -> dict:
        return {
            "app_id": self.feishu_app_id,
            "app_secret": self.feishu_app_secret,
            "webhook_url": self.feishu_webhook_url,
            "verification_token": self.feishu_verification_token,
            "encrypt_key": self.feishu_encrypt_key,
        }
