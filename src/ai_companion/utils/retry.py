"""
Retry utilities with exponential backoff.
Inspired by claw0's exponential backoff pattern.
"""

import time
import random
from typing import Callable, TypeVar, Optional

T = TypeVar("T")


def exponential_backoff(
    attempts: int,
    base_delay: float = 5.0,
    max_delay: float = 600.0,
    jitter: float = 0.1
) -> float:
    """
    Calculate exponential backoff delay: base_delay^attempts + jitter.

    From claw0 s08_delivery: 5s → 25s → 2min → 10min
    """
    delay = base_delay * (5 ** (attempts - 1))
    delay = min(delay, max_delay)
    if jitter > 0:
        delay += random.uniform(-jitter * delay, jitter * delay)
    return max(delay, 0)


def retry_with_backoff(
    func: Callable[[], T],
    max_attempts: int = 4,
    base_delay: float = 5.0,
    max_delay: float = 600.0,
    jitter: float = 0.1,
    retry_on_exceptions: tuple[type[Exception], ...] = (Exception,)
) -> T:
    """
    Retry a function with exponential backoff.
    """
    last_exception: Optional[Exception] = None

    for attempt in range(1, max_attempts + 1):
        try:
            return func()
        except retry_on_exceptions as e:
            last_exception = e
            if attempt < max_attempts:
                delay = exponential_backoff(attempt, base_delay, max_delay, jitter)
                time.sleep(delay)

    raise last_exception  # type: ignore
