"""
Exponential backoff for failed deliveries.
From claw0 s08: 5s → 25s → 2min → 10min
"""


def calculate_backoff(attempt: int, base: float = 5.0, max_delay: float = 600.0) -> float:
    """
    Calculate backoff delay using exponential growth.
    attempt starts at 1.
    """
    # 5^attempt: 5^1 = 5, 5^2 = 25, 5^3 = 125 (2min), 5^4 = 625 (~10min)
    delay = base * (5 ** (attempt - 1))
    return min(delay, max_delay)
