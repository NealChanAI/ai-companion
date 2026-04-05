"""
Generation tracking for concurrent processing.
From claw0 s10: Track which generation is current,
so outdated requests can be ignored.
"""

import threading
from typing import Dict


class GenerationTracker:
    """
    Track generation counter per lane.
    When a new request comes in, increment generation.
    Any outdated generation results are ignored.
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._generations: Dict[str, int] = {}

    def next_generation(self, lane_name: str) -> int:
        """Get the next generation number for a lane."""
        with self._lock:
            current = self._generations.get(lane_name, 0)
            next_gen = current + 1
            self._generations[lane_name] = next_gen
            return next_gen

    def get_current(self, lane_name: str) -> int:
        """Get current generation number."""
        with self._lock:
            return self._generations.get(lane_name, 0)

    def is_current(self, lane_name: str, generation: int) -> bool:
        """Check if this generation is still current."""
        with self._lock:
            current = self._generations.get(lane_name, 0)
            return generation == current
