"""
API key rotation for resilience.
From claw0 s09: When one key fails, rotate to the next one.
"""

import itertools
from typing import List, Optional
from dataclasses import dataclass


@dataclass
class ApiKey:
    """An API key with usage tracking."""
    key: str
    name: str
    enabled: bool = True
    failures: int = 0


class KeyRotator:
    """
    Round-robin API key rotation.
    When one key fails, the next request uses the next key.
    Good for avoiding rate limits and increasing throughput.
    """

    def __init__(self, keys: List[str], names: Optional[List[str]] = None):
        self._keys: List[ApiKey] = []
        for i, key in enumerate(keys):
            name = names[i] if names and i < len(names) else f"key-{i+1}"
            self._keys.append(ApiKey(key=key, name=name))
        self._cycle = itertools.cycle(self._keys)

    def get_next(self) -> Optional[str]:
        """Get the next enabled key."""
        if not self._keys:
            return None

        # Try up to the number of keys to find an enabled one
        for _ in range(len(self._keys)):
            candidate = next(self._cycle)
            if candidate.enabled:
                return candidate.key
        return None

    def mark_failure(self, key: str) -> None:
        """Mark a key as failed (increase failure count)."""
        for k in self._keys:
            if k.key == key:
                k.failures += 1
                # If too many failures, disable it for now
                if k.failures >= 5:
                    k.enabled = False
                break

    def mark_success(self, key: str) -> None:
        """Mark a key as successful (reset failure count)."""
        for k in self._keys:
            if k.key == key:
                k.failures = 0
                k.enabled = True
                break

    def get_stats(self) -> List[dict]:
        """Get statistics about all keys."""
        return [
            {
                "name": k.name,
                "enabled": k.enabled,
                "failures": k.failures
            }
            for k in self._keys
        ]
