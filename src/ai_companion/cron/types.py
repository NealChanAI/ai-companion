"""
Runtime types for cron jobs.
"""

import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Any
from ai_companion.config.cron import CronJobConfig


@dataclass
class CronJob:
    """Runtime cron job state."""
    id: str
    config: CronJobConfig
    consecutive_errors: int = 0
    last_run_at: float = 0.0
    next_run_at: float = 0.0
    last_error: Optional[str] = None


@dataclass
class CronRunResult:
    """Result of a single cron run."""
    job_id: str
    status: str  # "ok", "error", "skipped"
    output: str = ""
    error: Optional[str] = None
    run_at: float = field(default_factory=time.time)
    duration_seconds: float = 0.0


@dataclass
class CronRunLog:
    """Persisted cron run log entry."""
    job_id: str
    run_at: str  # ISO format
    status: str
    output_preview: str = ""
    error: Optional[str] = None
    duration_seconds: float = 0.0
    tokens_used: Optional[dict] = None
