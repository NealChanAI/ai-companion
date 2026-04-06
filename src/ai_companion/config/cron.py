"""
Cron configuration schema.
Supports three schedule types: at, every, cron.
"""

from pydantic import BaseModel, Field
from typing import Optional, Union, List, Literal, Tuple


# Schedule types
class ScheduleAt(BaseModel):
    """One-time schedule."""
    kind: Literal["at"] = "at"
    at: str  # ISO format timestamp

    class Config:
        extra = "forbid"


class ScheduleEvery(BaseModel):
    """Fixed interval schedule."""
    kind: Literal["every"] = "every"
    every_seconds: int = Field(..., ge=1)
    anchor: Optional[str] = None  # ISO start time for alignment

    class Config:
        extra = "forbid"


class ScheduleCron(BaseModel):
    """Cron expression schedule."""
    kind: Literal["cron"] = "cron"
    expr: str  # 5-field cron expression
    timezone: Optional[str] = None  # IANA timezone

    class Config:
        extra = "forbid"


ScheduleConfig = Union[ScheduleAt, ScheduleEvery, ScheduleCron]


# Payload types
class PayloadAgentTurn(BaseModel):
    """Agent turn payload - runs a full agent turn."""
    kind: Literal["agent_turn"] = "agent_turn"
    message: str
    agent_id: Optional[str] = None
    model: Optional[str] = None

    class Config:
        extra = "forbid"


class PayloadSystemEvent(BaseModel):
    """System event payload - simple text notification."""
    kind: Literal["system_event"] = "system_event"
    text: str

    class Config:
        extra = "forbid"


PayloadConfig = Union[PayloadAgentTurn, PayloadSystemEvent]


# Delivery config
class DeliveryConfig(BaseModel):
    """Message delivery configuration."""
    mode: Literal["announce", "webhook", "none"] = "announce"
    channel: Optional[str] = None
    to: Optional[str] = None  # Recipient
    webhook_url: Optional[str] = None

    class Config:
        extra = "forbid"


# Retry config
class CronRetryConfig(BaseModel):
    """Retry configuration with exponential backoff."""
    max_attempts: int = Field(default=3, ge=1)
    backoff_seconds: List[int] = Field(default_factory=lambda: [30, 60, 300])

    class Config:
        extra = "forbid"


# Job config
class CronJobConfig(BaseModel):
    """Single cron job configuration."""
    id: str
    name: str
    enabled: bool = True
    schedule: ScheduleConfig
    payload: PayloadConfig
    delivery: DeliveryConfig = Field(default_factory=DeliveryConfig)
    retry: CronRetryConfig = Field(default_factory=CronRetryConfig)
    delete_after_run: bool = False  # For 'at' jobs

    class Config:
        extra = "forbid"


# Top-level config
class CronConfig(BaseModel):
    """Top-level cron configuration."""
    enabled: bool = True
    max_concurrent_runs: int = Field(default=3, ge=1)
    session_retention: Optional[str] = "24h"
    run_log_max_bytes: int = Field(default=2_000_000, ge=0)
    run_log_keep_lines: int = Field(default=2000, ge=0)

    class Config:
        extra = "forbid"
