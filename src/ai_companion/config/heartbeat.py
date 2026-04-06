"""
Heartbeat configuration schema.
Combines claw0's simplicity with OpenClaw's production features.
"""

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings
from typing import Tuple


class HeartbeatConfig(BaseSettings):
    """Heartbeat configuration for proactive agent checks.

    Features:
    - Configurable interval and active hours
    - Cost optimization with light_context mode
    - Session isolation for clean state
    - Visibility controls (show_ok, show_alerts, use_indicator)
    """

    # Basic scheduling
    enabled: bool = True
    interval_seconds: float = Field(default=60.0, ge=60.0)  # 1 minute default
    active_hours: Tuple[int, int] = Field(default=(9, 22), validation_alias="HEARTBEAT_ACTIVE_HOURS")  # 9 AM - 10 PM

    # Cost optimization
    light_context: bool = Field(default=True, validation_alias="HEARTBEAT_LIGHT_CONTEXT")  # Only read HEARTBEAT.md, skip other prompt layers
    isolated_session: bool = Field(default=False, validation_alias="HEARTBEAT_ISOLATED_SESSION")  # Run in isolated session, no conversation history

    # Visibility controls
    show_ok: bool = Field(default=False, validation_alias="HEARTBEAT_SHOW_OK")  # Send HEARTBEAT_OK acknowledgment
    show_alerts: bool = Field(default=True, validation_alias="HEARTBEAT_SHOW_ALERTS")  # Send alert messages
    use_indicator: bool = Field(default=False, validation_alias="HEARTBEAT_USE_INDICATOR")  # Emit indicator events for UIs

    # Queue control
    max_queue_size: int = Field(default=10, ge=1)

    # Target for sending messages
    default_target: str = Field(default="", validation_alias="HEARTBEAT_DEFAULT_TARGET")  # Default chat_id to send messages to
