"""
API Key Rotation Manager

Automatically rotates through multiple API keys when one fails.
Useful for avoiding rate limits and increasing quota.
"""

import os
from typing import List, Optional
from dataclasses import dataclass
import time


@dataclass
class APIKey:
    """Represents an API key with usage tracking."""

    key: str
    name: str  # Identifier (e.g., "project-1", "backup-1")
    failures: int = 0
    last_success: float = 0
    last_failure: float = 0
    is_exhausted: bool = False

    def mark_success(self):
        """Mark successful API call."""
        self.failures = 0
        self.last_success = time.time()
        self.is_exhausted = False

    def mark_failure(self, exhausted: bool = False):
        """Mark failed API call."""
        self.failures += 1
        self.last_failure = time.time()
        if exhausted or self.failures >= 3:
            self.is_exhausted = True


class APIKeyRotator:
    """
    Rotates through multiple API keys automatically.

    Features:
    - Try keys in sequence until one works
    - Mark exhausted keys and skip them
    - Reset exhausted keys after cooldown period
    - Health reporting
    """

    def __init__(
        self,
        keys: List[str],
        names: Optional[List[str]] = None,
        cooldown_minutes: int = 60,
    ):
        """
        Initialize with API keys.

        Args:
            keys: List of API key strings
            names: Optional names for each key (for logging)
            cooldown_minutes: Minutes before retrying exhausted keys
        """
        if not keys:
            raise ValueError("At least one API key required")

        self.keys = [
            APIKey(
                key=key, name=names[i] if names and i < len(names) else f"key-{i + 1}"
            )
            for i, key in enumerate(keys)
        ]

        self.current_index = 0
        self.cooldown_seconds = cooldown_minutes * 60

    def get_current_key(self) -> str:
        """Get the current active API key."""
        # Reset exhausted keys if cooldown period passed
        self._reset_cooled_down_keys()

        # Find next available key
        for _ in range(len(self.keys)):
            key_obj = self.keys[self.current_index]
            if not key_obj.is_exhausted:
                return key_obj.key
            # Move to next
            self.current_index = (self.current_index + 1) % len(self.keys)

        # All keys exhausted - return first one anyway (will fail but logged)
        return self.keys[0].key

    def get_current_key_name(self) -> str:
        """Get the name of current key."""
        return self.keys[self.current_index].name

    def mark_success(self):
        """Mark current key as successful."""
        self.keys[self.current_index].mark_success()

    def mark_failure(self, exhausted: bool = False):
        """
        Mark current key as failed and rotate to next.

        Args:
            exhausted: If True, marks key as exhausted (rate limit hit)
        """
        self.keys[self.current_index].mark_failure(exhausted)

        # Rotate to next key
        self.current_index = (self.current_index + 1) % len(self.keys)

    def _reset_cooled_down_keys(self):
        """Reset keys that have passed cooldown period."""
        now = time.time()
        for key in self.keys:
            if key.is_exhausted and key.last_failure:
                if (now - key.last_failure) >= self.cooldown_seconds:
                    key.is_exhausted = False
                    key.failures = 0

    def get_health_status(self) -> dict:
        """Get health status of all keys."""
        return {
            "total_keys": len(self.keys),
            "active_keys": len([k for k in self.keys if not k.is_exhausted]),
            "exhausted_keys": len([k for k in self.keys if k.is_exhausted]),
            "current_key": self.keys[self.current_index].name,
            "keys": [
                {
                    "name": k.name,
                    "status": "active" if not k.is_exhausted else "exhausted",
                    "failures": k.failures,
                    "last_success": k.last_success,
                    "last_failure": k.last_failure,
                }
                for k in self.keys
            ],
        }

    def all_exhausted(self) -> bool:
        """Check if all keys are exhausted."""
        return all(k.is_exhausted for k in self.keys)


def load_keys_from_env() -> APIKeyRotator:
    """
    Load Google API keys from environment.

    Looks for:
    - GOOGLE_API_KEY (primary)
    - GOOGLE_API_KEY_2, GOOGLE_API_KEY_3, GOOGLE_API_KEY_4, etc.
    """
    keys = []
    names = []

    # Primary key
    primary = os.getenv("GOOGLE_API_KEY") or os.getenv("JARVIS_API_KEY")
    if primary:
        keys.append(primary)
        names.append("primary")

    # Additional keys
    i = 2
    while True:
        key = os.getenv(f"GOOGLE_API_KEY_{i}")
        if not key:
            break
        keys.append(key)
        names.append(f"backup-{i - 1}")
        i += 1

    if not keys:
        raise ValueError("No Google API keys found in environment")

    return APIKeyRotator(keys, names, cooldown_minutes=60)


# Example usage:
# rotator = load_keys_from_env()
#
# while not rotator.all_exhausted():
#     api_key = rotator.get_current_key()
#     try:
#         result = call_api(api_key)
#         rotator.mark_success()
#         break
#     except RateLimitError:
#         rotator.mark_failure(exhausted=True)
#     except OtherError:
#         rotator.mark_failure(exhausted=False)
