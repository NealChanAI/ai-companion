"""
Retry with 3-layer retry onion.
From claw0 s09: 3-layer retry onion pattern.
"""

import time
from typing import Callable, TypeVar, Optional

T = TypeVar("T")


class RetryConfig:
    """Retry configuration."""
    def __init__(
        self,
        max_attempts: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
        exponential_backoff: bool = True
    ):
        self.max_attempts = max_attempts
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.exponential_backoff = exponential_backoff


def calculate_delay(attempt: int, config: RetryConfig) -> float:
    """Calculate delay for the nth attempt."""
    if config.exponential_backoff:
        delay = config.base_delay * (2 ** (attempt - 1))
    else:
        delay = config.base_delay
    return min(delay, config.max_delay)


def with_retry(
    func: Callable[[], T],
    config: RetryConfig | None = None
) -> T:
    """
    Execute function with retries.
    3-layer retry onion pattern from claw0 s09.
    """
    if config is None:
        config = RetryConfig()

    last_exception: Optional[Exception] = None

    for attempt in range(1, config.max_attempts + 1):
        try:
            return func()
        except Exception as e:
            last_exception = e
            if attempt < config.max_attempts:
                delay = calculate_delay(attempt, config)
                time.sleep(delay)

    raise last_exception  # type: ignore
